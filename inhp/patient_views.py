from datetime import date

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import password_validators_help_texts
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView
from django.utils.translation import gettext_lazy as _

from inhp.forms import MapiPatientForm
from inhp.models import Patient, VaccineExt, Mapi, Message, Vaccination


@login_required
def patient_change_password(request):
    user = request.user

    # On s’assure qu’on est bien sur un Patient et pas un Utilisateur pro
    if not isinstance(user, Patient):
        return redirect("home")

    if request.method == "POST":
        current_password = request.POST.get("current_password") or ""
        new_password1 = request.POST.get("new_password1") or ""
        new_password2 = request.POST.get("new_password2") or ""

        if not current_password or not new_password1 or not new_password2:
            messages.error(request, _("Veuillez remplir tous les champs."))
        elif not user.check_password(current_password):
            messages.error(request, _("Mot de passe actuel incorrect."))
        elif new_password1 != new_password2:
            messages.error(request, _("Les nouveaux mots de passe ne correspondent pas."))
        else:
            user.set_password(new_password1)
            user.must_change_password = False
            user.last_password_change = timezone.now()
            user.save()

            # Très important : garder l’utilisateur connecté après changement de mot de passe
            update_session_auth_hash(request, user)

            messages.success(request, _("Votre mot de passe a été modifié avec succès."))
            return redirect("patient_dashboard")

    return render(request, "patient_space/auth/change_password.html", {})


@login_required
def patient_password_policy(request):
    """
    Vue pour afficher la politique de mots de passe
    """
    user = request.user

    if not isinstance(user, Patient):
        return redirect("home")

    context = {
        'password_rules': password_validators_help_texts(),
        'min_length': 8,  # Longueur minimale recommandée
        'examples': {
            'good': [
                "M0tDeP@sseComplexe!",
                "VaccinCI-2024-Secure",
                "CotedIvoire@123Santé"
            ],
            'bad': [
                "12345678",
                "password",
                user.telephone1 if user.telephone1 else "0123456789"
            ]
        }
    }

    return render(request, "patient_space/auth/password_policy.html", context)


class PatientDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "patient_space/patient_dashboard.html"
    login_url = "login"  # ou '/login/' selon ton projet

    def dispatch(self, request, *args, **kwargs):
        """
        Sécurise l’accès : uniquement pour les patients.
        """
        if not isinstance(request.user, Patient):
            # Tu peux rediriger vers une page d'erreur ou home
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        patient: Patient = self.request.user
        today = date.today()

        # ---------------------------------------------------------------------
        # 1) VACCINATIONS (réelles)
        # ---------------------------------------------------------------------
        vaccinations_qs = (
            patient.historique_vaccinations
            .filter(deleted_at__isnull=True)
            .select_related("vaccin", "centre")
            .order_by("-date_vaccination")
        )

        vaccinations = list(vaccinations_qs)

        # Vaccinations externes (facultatif : tu peux les inclure dans les stats)
        vaccinations_ext_qs = (
            VaccineExt.objects.filter(
                patient=patient,
                deleted_at__isnull=True,
            )
            .select_related("vaccin")
            .order_by("-date")
        )
        vaccinations_ext = list(vaccinations_ext_qs)

        # ---------------------------------------------------------------------
        # 2) Vaccins uniques (types différents)
        # ---------------------------------------------------------------------
        vaccins_uniques = (
            vaccinations_qs
            .values("vaccin_id", "vaccin__nom")
            .distinct()
        )

        # ---------------------------------------------------------------------
        # 3) Prochain rappel (un seul) et rappels à venir
        #    (basé sur Vaccination.date_rappel)
        # ---------------------------------------------------------------------
        rappels_qs = (
            vaccinations_qs
            .filter(date_rappel__isnull=False, date_rappel__gte=today)
            .order_by("date_rappel")
        )

        prochain_rappel = rappels_qs.first()

        # Liste plus large des rappels à venir
        rappels_prochains = []
        for v in rappels_qs[:10]:  # limite à 10 pour le calendrier
            jours_restants = (v.date_rappel - today).days
            urgent = jours_restants <= 7  # à ajuster si besoin
            rappels_prochains.append({
                "vaccin": v.vaccin,
                "dose": v.dose,
                "date": v.date_rappel,
                "jours_restants": jours_restants,
                "urgent": urgent,
            })

        # ---------------------------------------------------------------------
        # 4) Dernières vaccinations (cartes à droite)
        # ---------------------------------------------------------------------
        # On prend les 4 dernières vaccinations pour les cartes "Dernières vaccinations"
        derniers_vaccinations_qs = vaccinations_qs[:4]

        # Petites palettes de couleurs/icônes Tailwind pour les cartes
        palette_couleurs = ["emerald", "sky", "amber", "violet"]
        palette_icones = [
            "fa-syringe",  # générique vaccin
            "fa-shield-virus",  # virus
            "fa-baby",  # vaccins infantiles
            "fa-notes-medical",  # dossier médical
        ]

        derniers_vaccinations = []
        for idx, v in enumerate(derniers_vaccinations_qs):
            couleur = palette_couleurs[idx % len(palette_couleurs)]
            icone = palette_icones[idx % len(palette_icones)]

            # Détermine un statut simple
            if v.date_rappel and v.date_rappel < today:
                statut = "Rappel en retard"
            elif v.date_rappel and v.date_rappel >= today:
                statut = "Rappel prévu"
            else:
                statut = "Réalisé"

            derniers_vaccinations.append({
                "id": v.id,
                "vaccin": v.vaccin,
                "dose": v.dose,
                "date_vaccination": v.date_vaccination,
                "centre": v.centre,
                "statut": statut,
                "couleur": couleur,
                "icone": icone,
            })

        # ---------------------------------------------------------------------
        # 5) Statut global du calendrier vaccinal
        # ---------------------------------------------------------------------
        # simple logique :
        # - si rappel en retard => "Rappels en retard"
        # - sinon si rappel futur => "Rappels à venir"
        # - sinon => "Calendrier à jour"
        rappel_en_retard = vaccinations_qs.filter(
            date_rappel__isnull=False,
            date_rappel__lt=today
        ).exists()

        if rappel_en_retard:
            statut_calendrier = "Rappels en retard"
            statut_calendrier_color = "red"
        elif prochain_rappel:
            statut_calendrier = "Rappels à venir"
            statut_calendrier_color = "amber"
        else:
            statut_calendrier = "Calendrier à jour"
            statut_calendrier_color = "emerald"

        # ---------------------------------------------------------------------
        # 6) MAPI (Effets indésirables déclarés)
        # ---------------------------------------------------------------------
        mapi_qs = Mapi.objects.filter(
            patient=patient,
            deleted_at__isnull=True,
        ).order_by("-date")

        nb_mapi = mapi_qs.count()
        derniers_mapi = mapi_qs[:3]  # Liste des 5 derniers

        # ---------------------------------------------------------------------
        # 7) Messages (si tu veux pousser des infos patient)
        #    Ici j'utilise Message global (utilisateur), à adapter selon ton modèle
        # ---------------------------------------------------------------------
        messages_info_qs = (
            Message.objects.filter(
                deleted_at__isnull=True,
                is_active=True,
            )
            .order_by("-created_at")[:5]
        )

        # ---------------------------------------------------------------------
        # 8) must_change_password (déjà sur le modèle Patient)
        # ---------------------------------------------------------------------
        must_change_password = patient.must_change_password

        # ---------------------------------------------------------------------
        # 9) Centre actuel
        # ---------------------------------------------------------------------
        centre_actuel = patient.centre_actuel or patient.centre

        # ---------------------------------------------------------------------
        # 10) Contexte
        # ---------------------------------------------------------------------
        ctx.update({
            "patient": patient,
            "vaccinations": vaccinations,
            "vaccinations_ext": vaccinations_ext,
            "vaccins_uniques": vaccins_uniques,
            "prochain_rappel": prochain_rappel,
            "rappels_prochains": rappels_prochains,
            "derniers_vaccinations": derniers_vaccinations,
            "statut_calendrier": statut_calendrier,
            "statut_calendrier_color": statut_calendrier_color,
            "nb_mapi": nb_mapi,
            "derniers_mapi": derniers_mapi,
            "messages_info": messages_info_qs,
            "must_change_password": must_change_password,
            "centre_actuel": centre_actuel,
        })
        return ctx


@login_required
def patient_mapi_create_view(request, vaccination_id=None):
    """
    Permet à un patient connecté de déclarer un MAPI (effet indésirable).
    - Vérifie que l'utilisateur est bien un Patient
    - Préselectionne éventuellement une vaccination passée en paramètre
    """

    user = request.user
    if not isinstance(user, Patient):
        messages.error(request, _("Vous n'êtes pas autorisé à accéder à cette page."))
        return redirect("home")

    patient = user

    initial = {}
    preselected_vaccination = None
    if vaccination_id:
        preselected_vaccination = get_object_or_404(
            Vaccination,
            id=vaccination_id,
            patient=patient,
            deleted_at__isnull=True
        )
        initial["vaccination"] = preselected_vaccination

    if request.method == "POST":
        form = MapiPatientForm(request.POST, patient=patient)
        if form.is_valid():
            mapi = form.save(commit=False)
            mapi.patient = patient

            # Centre = centre de la vaccination, sinon centre actuel du patient
            if mapi.vaccination and mapi.vaccination.centre:
                mapi.centre = mapi.vaccination.centre
            else:
                mapi.centre = patient.centre_actuel or patient.centre

            # Date de déclaration = maintenant
            mapi.date = timezone.now()

            # Déclaration par le patient => pas d'utilisateur professionnel associé
            mapi.utilisateur = None

            mapi.save()

            messages.success(
                request,
                _(
                    "Votre déclaration d'effet indésirable a été enregistrée. "
                    "Un professionnel de santé pourra vous recontacter si nécessaire."
                ),
            )
            return redirect("patient_dashboard")
    else:
        form = MapiPatientForm(patient=patient, initial=initial)

    context = {
        "patient": patient,
        "form": form,
        "vaccination": preselected_vaccination,
    }

    return render(request, "patient_space/mapi_report.html", context)
