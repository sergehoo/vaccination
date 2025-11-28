# /vaccination/inhp/backends.py

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
)
from django.contrib.auth.backends import ModelBackend, BaseBackend
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import AccessMixin
from django.http import request
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from inhp.models import Patient, AccessLevel, Utilisateur

logger = logging.getLogger(__name__)
UserModel = get_user_model()


# ======================================================================
#  BACKENDS D'AUTHENTIFICATION
# ======================================================================

class PatientAuthBackend(ModelBackend):
    """
    Backend d'authentification pour les patients.

    - Identifiant : code_patient (ou email)
    - Première connexion / migration :
        si last_password_change est NULL
        => on autorise code_patient + telephone1
        => on bascule sur un vrai mot de passe hashé
    """

    def authenticate(self, request, username=None, password=None, user_type=None, **kwargs):
        # 🔐 Ne répondre qu'aux logins patient
        if user_type not in ("patient", None):
            return None

        if username is None or password is None:
            return None

        identifier = str(username).strip()

        # 1) Récupération du patient (code_patient d'abord, puis email)
        patient = None
        try:
            patient = Patient.objects.get(
                code_patient=identifier,
                deleted_at__isnull=True,
            )
        except Patient.DoesNotExist:
            if "@" in identifier:
                try:
                    patient = Patient.objects.get(
                        email__iexact=identifier,
                        deleted_at__isnull=True,
                    )
                except Patient.DoesNotExist:
                    logger.info(
                        "[PatientAuth] Aucun patient trouvé pour identifiant=%s",
                        identifier[:10],
                    )
                    return None
                except Exception as e:
                    logger.error(
                        "[PatientAuth] Erreur récupération patient identifiant=%s : %s",
                        identifier[:10],
                        e,
                    )
                    return None
            else:
                logger.info(
                    "[PatientAuth] Tentative patient échouée (ni code_patient ni email) identifiant=%s",
                    identifier[:10],
                )
                return None
        except Exception as e:
            logger.error(
                "[PatientAuth] Erreur récupération patient identifiant=%s : %s",
                identifier[:10],
                e,
            )
            return None

        # 2) Vérifications d'état
        if not getattr(patient, "is_active", True):
            logger.warning("[PatientAuth] Patient inactif identifiant=%s", identifier[:10])
            return None

        if hasattr(patient, "is_account_locked") and patient.is_account_locked():
            logger.warning(
                "[PatientAuth] Compte patient verrouillé identifiant=%s (jusqu'à %s)",
                identifier[:10],
                patient.account_locked_until,
            )
            return None

        # 3) Cas standard : mot de passe déjà défini
        if hasattr(patient, "has_usable_password") and patient.has_usable_password() and getattr(
                patient, "last_password_change", None
        ):
            if patient.check_password(password):
                if getattr(patient, "failed_login_attempts", 0) or getattr(patient, "account_locked_until", None):
                    patient.failed_login_attempts = 0
                    patient.account_locked_until = None
                    patient.save(update_fields=["failed_login_attempts", "account_locked_until"])
                logger.info("[PatientAuth] Connexion patient OK identifiant=%s", identifier[:10])
                return patient

            self._handle_failed_login(patient, identifier)
            return None

        # 4) Première connexion / migration : téléphone comme mot de passe initial
        tel = (getattr(patient, "telephone1", "") or "").strip()
        if tel and password == tel:
            logger.info("[PatientAuth] Première connexion / migration pour patient identifiant=%s", identifier[:10])
            patient.set_password(password)
            patient.last_password_change = timezone.now()
            if hasattr(patient, "must_change_password"):
                patient.must_change_password = True
            patient.failed_login_attempts = 0
            patient.account_locked_until = None
            patient.save(
                update_fields=[
                    "password",
                    "last_password_change",
                    "failed_login_attempts",
                    "account_locked_until",
                    *(["must_change_password"] if hasattr(patient, "must_change_password") else []),
                ]
            )
            return patient

        # 5) Sinon : mot de passe incorrect
        self._handle_failed_login(patient, identifier)
        return None

    def _handle_failed_login(self, patient, identifier: str):
        """
        Gestion centralisée des tentatives échouées + verrouillage.
        """
        patient.failed_login_attempts += 1
        patient.last_failed_login = timezone.now()

        # Exemple : verrouillage après 5 tentatives
        if patient.failed_login_attempts >= 5:
            patient.account_locked_until = timezone.now() + timezone.timedelta(hours=1)
            logger.warning(
                "[PatientAuth] Compte patient verrouillé après %s tentatives, identifiant=%s",
                patient.failed_login_attempts,
                identifier[:10],
            )

        patient.save(update_fields=["failed_login_attempts", "last_failed_login", "account_locked_until"])
        logger.warning("[PatientAuth] Mot de passe incorrect pour identifiant=%s", identifier[:10])

    def get_user(self, user_id):
        try:
            return Patient.objects.get(pk=user_id, is_active=True, deleted_at__isnull=True)
        except Patient.DoesNotExist:
            return None


# class ProfessionalAuthBackend(ModelBackend):
#     def authenticate(self, request, username=None, password=None, **kwargs):
#         if username is None or password is None:
#             return None
#
#         email = str(username).strip()
#
#         try:
#             # insensible à la casse
#             user = UserModel.objects.get(email__iexact=email)
#         except UserModel.DoesNotExist:
#             logger.info("Tentative de connexion pro échouée pour email=%s", email[:30])
#             return None
#         except Exception as e:
#             logger.error("Erreur lors de la récupération de l'utilisateur email=%s : %s", email[:30], e)
#             return None
#
#         if not user.is_active:
#             logger.warning("Utilisateur inactif email=%s", email[:30])
#             return None
#
#         if user.check_password(password):
#             return user
#
#         logger.warning("Mot de passe incorrect pour utilisateur email=%s", email[:30])
#         return None

# ======================================================================
#  LOGIQUE DE REDIRECTION APRÈS LOGIN
# ======================================================================
class ProfessionalAuthBackend(BaseBackend):
    """
    Backend d'authentification pour les professionnels de santé.
    Auth sur le modèle Utilisateur (email + mot de passe).
    """

    def authenticate(self, request, username=None, password=None, user_type=None, **kwargs):
        # ⬅️ ne répondre qu'aux connexions pro
        if user_type not in ("professional", None):
            return None

        if username is None or password is None:
            return None

        email = str(username).strip().lower()

        try:
            user = Utilisateur.objects.get(email__iexact=email)
        except Utilisateur.DoesNotExist:
            logger.info(
                "[ProAuth] Aucun Utilisateur trouvé pour email=%s",
                email[:50],
            )
            return None
        except Exception as e:
            logger.error(
                "[ProAuth] Erreur lors de la récupération de l'utilisateur email=%s : %s",
                email[:50],
                e,
            )
            return None

        if not user.is_active:
            logger.warning("[ProAuth] Utilisateur inactif email=%s", email[:50])
            return None

        if user.check_password(password):
            logger.info(
                "[ProAuth] Auth OK pour email=%s (id=%s)",
                email[:50],
                user.pk,
            )
            return user

        logger.warning(
            "[ProAuth] Mot de passe incorrect pour email=%s",
            email[:50],
        )
        return None

    def get_user(self, user_id):
        try:
            return Utilisateur.objects.get(pk=user_id, is_active=True)
        except Utilisateur.DoesNotExist:
            return None
    def get_user(self, user_id):
        try:
            return Utilisateur.objects.get(pk=user_id, is_active=True)
        except Utilisateur.DoesNotExist:
            return None


def get_redirect_url_for_user(user):
    """
    Détermine la URL de redirection après connexion selon le type d'utilisateur.
    - Patient  -> espace patient
    - Staff/superuser -> dashboard national (ou admin)
    - Pro -> selon access_level, sinon centre
    """
    try:
        # 1) Patients (modèle Patient)
        if isinstance(user, Patient):
            # Si tu forces un changement de mot de passe à la première connexion
            if getattr(user, "must_change_password", False):
                return reverse("patient_change_password")
            return reverse("patient_dashboard")

        # 2) Professionnels (AUTH_USER_MODEL = Utilisateur)
        if isinstance(user, UserModel):
            # Superuser / staff -> admin ou dashboard national
            if user.is_superuser or user.is_staff:
                # return reverse("admin:index")
                return reverse("dashboard_national")

            access_level = getattr(user, "access_level", None)

            if access_level == AccessLevel.NATIONAL:
                return reverse("dashboard_national")
            if access_level == AccessLevel.POLE:
                return reverse("dashboard_pole")
            if access_level == AccessLevel.REGION:
                return reverse("dashboard_region")
            if access_level == AccessLevel.DISTRICT:
                return reverse("dashboard_district")

            # Par défaut : dashboard centre
            return reverse("dashboard_centre")

        # 3) Fallback générique
        return reverse("home")

    except Exception as e:
        logger.error("Erreur dans get_redirect_url_for_user pour user=%s : %s", user, e)
        # Fallback ultime
        return reverse("home")


# ======================================================================
#  VUES DE LOGIN / LOGOUT UNIFIÉES
# ======================================================================


logger = logging.getLogger(__name__)


@sensitive_post_parameters("password")
@csrf_protect
@never_cache
def login_unifie_view(request):
    """
    Vue de connexion unifiée sécurisée pour patients ET professionnels.

    - user_type = 'professional' -> Utilisateur (email)
    - user_type = 'patient'      -> Patient (code_patient)
    """

    # Si déjà connecté -> on ne repasse pas par la page de login
    if request.user.is_authenticated:
        return redirect(get_redirect_url_for_user(request.user))

    identifier = ""
    user_type = "professional"

    if request.method == "POST":
        user_type = request.POST.get("user_type", "professional")
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""

        # Validation basique
        if not identifier or not password:
            messages.error(request, _("Veuillez renseigner tous les champs obligatoires."))
            return render(
                request,
                "auth/login.html",
                {"identifier": identifier, "user_type": user_type},
            )

        # ==========================
        # 1) GESTION SPÉCIFIQUE PATIENT
        # ==========================
        patient_obj = None
        if user_type == "patient" and identifier:
            patient_obj = Patient.objects.filter(code_patient=identifier).first()

            # 🔒 Si déjà verrouillé avant même l'authentification
            if patient_obj and patient_obj.is_account_locked():
                locked_until = localtime(patient_obj.account_locked_until)
                messages.error(
                    request,
                    _(
                        "Votre compte patient est verrouillé après plusieurs tentatives de connexion. "
                        "Il sera de nouveau accessible à partir du %(date)s."
                    )
                    % {
                        "date": locked_until.strftime("%d/%m/%Y à %H:%M"),
                    },
                )
                logger.warning(
                    "[PatientAuth] Tentative de connexion sur compte verrouillé - identifiant=%s..., IP=%s",
                    identifier[:10],
                    request.META.get("REMOTE_ADDR"),
                )

                return render(
                    request,
                    "auth/login.html",
                    {"identifier": identifier, "user_type": user_type},
                )

        # ==========================
        # 2) AUTHENTIFICATION
        # ==========================
        try:
            user = authenticate(
                request,
                username=identifier,
                password=password,
                user_type=user_type,  # 👈 clé pour que chaque backend sache s’il doit répondre
            )

            if user is None:
                # Cas particulier : le backend vient de verrouiller le compte patient
                if (
                    user_type == "patient"
                    and patient_obj is not None
                    and patient_obj.is_account_locked()
                ):
                    locked_until = localtime(patient_obj.account_locked_until)
                    messages.error(
                        request,
                        _(
                            "Votre compte patient vient d'être verrouillé après plusieurs tentatives de connexion. "
                            "Il sera de nouveau accessible à partir du %(date)s."
                        )
                        % {
                            "date": locked_until.strftime("%d/%m/%Y à %H:%M"),
                        },
                    )
                    logger.warning(
                        "[PatientAuth] Compte patient verrouillé identifiant=%s..., IP=%s",
                        identifier[:10],
                        request.META.get("REMOTE_ADDR"),
                    )
                else:
                    # Message générique pour toutes les autres erreurs d'identifiants
                    messages.error(
                        request,
                        _("Identifiants incorrects ou compte inactif. Veuillez réessayer."),
                    )
                    logger.warning(
                        "Tentative de connexion échouée - type=%s, identifiant=%s..., IP=%s",
                        user_type,
                        identifier[:10],
                        request.META.get("REMOTE_ADDR"),
                    )

                # (optionnel) gestion du compteur de tentatives par session
                if hasattr(request, "session"):
                    request.session["login_attempts"] = request.session.get(
                        "login_attempts", 0
                    ) + 1

            else:
                # Succès : login + reset compteur
                login(request, user)

                if hasattr(request, "session"):
                    request.session["login_attempts"] = 0

                logger.info(
                    "Connexion réussie - type=%s, user=%s (id=%s), IP=%s",
                    user_type,
                    getattr(user, "email", getattr(user, "code_patient", "N/A")),
                    user.pk,
                    request.META.get("REMOTE_ADDR"),
                )

                messages.success(request, _("Connexion réussie. Bienvenue dans votre espace."))
                return redirect(get_redirect_url_for_user(user))

        except Exception as e:
            logger.exception("Erreur lors de l'authentification unifiée : %s", e)
            messages.error(
                request,
                _("Une erreur technique s'est produite. Veuillez réessayer."),
            )

    # GET ou POST avec erreur -> on réaffiche la page
    return render(
        request,
        "auth/login.html",
        {
            "identifier": identifier,
            "user_type": user_type,
        },
    )

@require_http_methods(["GET", "POST"])
@csrf_protect
@login_required
def logout_view(request):
    """
    Vue de déconnexion sécurisée avec journalisation avancée et protection CSRF.
    """
    user = request.user
    user_info = {
        'username': getattr(user, 'username', 'N/A'),
        'email': getattr(user, 'email', 'N/A'),
        'user_id': getattr(user, 'id', 'N/A'),
        'ip_address': _get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', 'N/A')[:500],
        'timestamp': timezone.now().isoformat()
    }

    # Journalisation détaillée
    logger.info(
        "Tentative de déconnexion de l'utilisateur: %s (ID: %s) depuis %s",
        user_info['username'],
        user_info['user_id'],
        user_info['ip_address']
    )

    # Vérification supplémentaire pour les requêtes POST (recommandé)
    if request.method == 'POST':
        return _perform_logout(request, user_info)

    # Pour les requêtes GET, afficher une page de confirmation
    return _render_logout_confirmation(request, user_info)


def _perform_logout(request, user_info):
    """
    Effectue la déconnexion réelle de l'utilisateur.
    """
    try:
        # Journalisation avant déconnexion
        logger.info(
            "Déconnexion en cours pour l'utilisateur: %s (ID: %s)",
            user_info['username'],
            user_info['user_id']
        )

        # Déconnexion Django standard
        auth_logout(request)

        # Nettoyage de session personnalisé si nécessaire
        _cleanup_session(request)

        # Journalisation du succès
        logger.info(
            "Déconnexion réussie pour l'utilisateur: %s (ID: %s)",
            user_info['username'],
            user_info['user_id']
        )

        # Message de succès
        messages.success(
            request,
            _("Vous avez été déconnecté avec succès. À bientôt !"),
            extra_tags='success logout'
        )

        # Redirection avec paramètres de sécurité
        response = redirect(_get_redirect_url(request))

        # Nettoyage des cookies de session
        _secure_logout_response(response, request)

        return response

    except Exception as e:
        # Journalisation des erreurs
        logger.error(
            "Erreur lors de la déconnexion de l'utilisateur %s (ID: %s): %s",
            user_info['username'],
            user_info['user_id'],
            str(e),
            exc_info=True
        )

        messages.error(
            request,
            _("Une erreur s'est produite lors de la déconnexion. Veuillez réessayer."),
            extra_tags='error logout'
        )
        return redirect('home')


def _render_logout_confirmation(request, user_info):
    """
    Affiche une page de confirmation de déconnexion.
    """
    from django.shortcuts import render

    context = {
        'username': user_info['username'],
        'ip_address': user_info['ip_address'],
        'last_login': getattr(request.user, 'last_login', None),
        'current_time': timezone.now(),
    }

    return render(request, 'auth/logout_confirm.html', context)


def _get_client_ip(request):
    """
    Récupère l'adresse IP réelle du client.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _cleanup_session(request):
    """
    Nettoie les données de session sensibles.
    """
    try:
        # Supprimer les données sensibles de la session
        sensitive_keys = [
            'user_id', 'auth_token', 'oauth_state',
            'temp_data', 'wizard_data'
        ]

        for key in sensitive_keys:
            if key in request.session:
                del request.session[key]

        # Sauvegarder les modifications
        request.session.save()

    except Exception as e:
        logger.warning("Erreur lors du nettoyage de session: %s", str(e))


def _secure_logout_response(response, request):
    """
    Applique des mesures de sécurité supplémentaires à la réponse.
    """
    # Supprimer le cookie de session
    if settings.SESSION_COOKIE_NAME in request.COOKIES:
        response.delete_cookie(
            settings.SESSION_COOKIE_NAME,
            path=settings.SESSION_COOKIE_PATH,
            domain=settings.SESSION_COOKIE_DOMAIN,
        )

    # Supprimer d'autres cookies sensibles si nécessaire
    sensitive_cookies = ['csrftoken', 'remember_token']
    for cookie_name in sensitive_cookies:
        if cookie_name in request.COOKIES:
            response.delete_cookie(cookie_name)

    # Headers de sécurité
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response


def _get_redirect_url(request):
    """
    Détermine l'URL de redirection après déconnexion.
    """
    # Priorité aux paramètres next
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and _is_safe_url(next_url):
        return next_url

    # URL par défaut selon le contexte
    default_urls = getattr(settings, 'LOGOUT_REDIRECT_URLS', ['login', 'home'])

    for url_name in default_urls:
        try:
            from django.urls import reverse
            return reverse(url_name)
        except:
            continue

    # Fallback
    return '/'


def _is_safe_url(url):
    """
    Vérifie si l'URL est safe pour la redirection.
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    allowed_hosts = set(settings.ALLOWED_HOSTS)
    if settings.DEBUG:
        allowed_hosts.add('localhost')
        allowed_hosts.add('127.0.0.1')

    return url_has_allowed_host_and_scheme(
        url,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure()
    )


class StaffOnlyMixin(AccessMixin):
    login_url = "login"  # name de ta vue login_unifie_view

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # 1) Pas connecté → retour login
        if not user.is_authenticated:
            return redirect(self.login_url)

        # 2) Patient authentifié → on le renvoie gentiment vers son espace
        if isinstance(user, Patient):
            messages.error(request, _("Accès réservé au personnel sanitaire."))
            return redirect("patient_dashboard")

        # 4) Pro et staff → pas le droit d’aller sur ces vues
        if not getattr(user, "is_staff", False):
            messages.error(request, _("Vous n'avez pas les droits pour accéder à cette section."))
            return redirect(self.login_url)

        # 4) OK : staff / superuser
        return super().dispatch(request, *args, **kwargs)
