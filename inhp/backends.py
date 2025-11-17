# /vaccination/inhp/backends.py

import logging

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
)
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from inhp.models import Patient, AccessLevel

logger = logging.getLogger(__name__)
UserModel = get_user_model()


# ======================================================================
#  BACKENDS D'AUTHENTIFICATION
# ======================================================================

class PatientAuthBackend(ModelBackend):
    """
    Backend d'authentification pour les patients.

    - Identifiant : code_patient (ou email si tu veux garder ça)
    - Première connexion / migration :
        si last_password_change est NULL
        => on autorise code_patient + telephone1
        => on bascule sur un vrai mot de passe hashé
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        identifier = str(username).strip()

        # 1) Récupération du patient (code_patient d'abord, puis éventuel email)
        patient = None
        try:
            patient = Patient.objects.get(
                code_patient=identifier,
                deleted_at__isnull=True,
            )
        except Patient.DoesNotExist:
            # Optionnel : login par email si l'identifiant contient un @
            if "@" in identifier:
                try:
                    patient = Patient.objects.get(
                        email__iexact=identifier,
                        deleted_at__isnull=True,
                    )
                except Patient.DoesNotExist:
                    logger.info(
                        "Tentative de connexion patient échouée identifiant=%s",
                        identifier[:10],
                    )
                    return None
                except Exception as e:
                    logger.error(
                        "Erreur lors de la récupération du patient identifiant=%s : %s",
                        identifier[:10],
                        e,
                    )
                    return None
            else:
                logger.info(
                    "Tentative patient échouée (ni code_patient ni email) identifiant=%s",
                    identifier[:10],
                )
                return None
        except Exception as e:
            logger.error(
                "Erreur lors de la récupération du patient identifiant=%s : %s",
                identifier[:10],
                e,
            )
            return None

        # 2) Vérifications d'état
        if not patient.is_active:
            logger.warning("Patient inactif identifiant=%s", identifier[:10])
            return None

        if patient.is_account_locked():
            logger.warning(
                "Compte patient verrouillé identifiant=%s (jusqu'à %s)",
                identifier[:10],
                patient.account_locked_until,
            )
            return None

        # 3) CAS 1 : patient déjà passé sur un vrai mot de passe
        # (last_password_change non nul => on utilise le flux "normal")
        if patient.has_usable_password() and patient.last_password_change:
            if patient.check_password(password):
                # succès : reset sécurité
                if patient.failed_login_attempts or patient.account_locked_until:
                    patient.failed_login_attempts = 0
                    patient.account_locked_until = None
                    patient.save(update_fields=["failed_login_attempts", "account_locked_until"])
                return patient

            # mot de passe incorrect
            self._handle_failed_login(patient, identifier)
            return None

        # 4) CAS 2 : première connexion / migration
        #    On autorise "telephone1 comme mot de passe initial"
        tel = (patient.telephone1 or "").strip()
        if tel and password == tel:
            logger.info(
                "Première connexion / migration pour patient identifiant=%s",
                identifier[:10],
            )
            # On bascule sur un vrai mot de passe hashé
            patient.set_password(password)
            patient.last_password_change = timezone.now()
            patient.must_change_password = True  # tu peux l'utiliser pour forcer un changement
            patient.failed_login_attempts = 0
            patient.account_locked_until = None
            patient.save(
                update_fields=[
                    "password",
                    "last_password_change",
                    "must_change_password",
                    "failed_login_attempts",
                    "account_locked_until",
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
                "Compte patient verrouillé après %s tentatives, identifiant=%s",
                patient.failed_login_attempts,
                identifier[:10],
            )

        patient.save(update_fields=["failed_login_attempts", "last_failed_login", "account_locked_until"])
        logger.warning("Mot de passe incorrect pour patient identifiant=%s", identifier[:10])

    def get_user(self, user_id):
        try:
            return Patient.objects.get(pk=user_id, is_active=True, deleted_at__isnull=True)
        except Patient.DoesNotExist:
            return None


class ProfessionalAuthBackend(ModelBackend):
    """
    Backend d'authentification pour les professionnels de santé.
    Auth via email (USERNAME_FIELD de Utilisateur) + mot de passe.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        username = email (USERNAME_FIELD de ton Utilisateur)
        """
        if username is None or password is None:
            return None

        email = str(username).strip().lower()

        try:
            user = UserModel.objects.get(email=email, is_active=True)
        except UserModel.DoesNotExist:
            logger.info(
                "Tentative de connexion pro échouée pour email=%s",
                email[:30],
            )
            return None
        except Exception as e:
            logger.error(
                "Erreur lors de la récupération de l'utilisateur email=%s : %s",
                email[:30],
                e,
            )
            return None

        if user.check_password(password):
            return user

        logger.warning(
            "Mot de passe incorrect pour utilisateur email=%s",
            email[:30],
        )
        return None


# ======================================================================
#  LOGIQUE DE REDIRECTION APRÈS LOGIN
# ======================================================================

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

        # Rate limiting basique via la session
        # if hasattr(request, "session"):
        #     attempts = request.session.get("login_attempts", 0)
        #     if attempts >= 10:
        #         messages.error(
        #             request,
        #             _("Trop de tentatives de connexion. Veuillez réessayer plus tard."),
        #         )
        #         logger.warning(
        #             "Blocage temporaire après trop de tentatives - IP=%s",
        #             request.META.get("REMOTE_ADDR"),
        #         )
        #         return render(
        #             request,
        #             "auth/login.html",
        #             {"identifier": identifier, "user_type": user_type},
        #         )
        #
        # user = None

        try:
            if user_type == "professional":
                # Utilisateur : email comme username
                user = authenticate(
                    request,
                    backend="inhp.backends.ProfessionalAuthBackend",
                    username=identifier,
                    password=password,
                )
            else:
                # Patient : code_patient comme username
                user = authenticate(
                    request,
                    backend="inhp.backends.PatientAuthBackend",
                    username=identifier,
                    password=password,
                )

            if user is None:
                # Incrément du compteur seulement en cas d'échec
                if hasattr(request, "session"):
                    request.session["login_attempts"] = request.session.get(
                        "login_attempts", 0
                    ) + 1

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


def logout_view(request):
    """
    Vue de déconnexion sécurisée.
    """
    if request.user.is_authenticated:
        logger.info("Déconnexion de l'utilisateur: %s", request.user)

    auth_logout(request)
    messages.success(request, _("Vous avez été déconnecté avec succès."))
    return redirect("login")


class StaffOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if isinstance(user, Patient):
            messages.error(request, _("Accès réservé au personnel sanitaire."))
            return redirect("patient_dashboard")

        if not user.is_authenticated or not user.is_staff:
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)