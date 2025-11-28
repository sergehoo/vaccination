from datetime import date, timedelta, datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import password_validators_help_texts
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView, View
from django.utils.translation import gettext_lazy as _

from inhp.forms import MapiPatientForm, RendezVousVaccinationForm, AnnulationRendezVousForm
from inhp.models import Patient, VaccineExt, Mapi, Message, Vaccination, RendezVousStatut, RendezVousVaccination, \
    RendezVousType, RendezVousCanal, PrioriteRendezVous


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
    login_url = "login"

    def dispatch(self, request, *args, **kwargs):
        if not isinstance(request.user, Patient):
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        patient: Patient = self.request.user
        today = date.today()
        now = timezone.now()

        # -----------------------------------------------------------------
        # 11) Enfants suivis par ce parent (patient responsable)
        # -----------------------------------------------------------------
        enfants_qs = (
            patient.enfants_suivis
            .filter(deleted_at__isnull=True)
            .select_related("centre")
            .order_by("nom", "prenoms")
        )

        enfants_data = []

        for enfant in enfants_qs:
            # Vaccinations de l'enfant
            vaccs_enfant_qs = (
                enfant.historique_vaccinations
                .filter(deleted_at__isnull=True)
                .select_related("vaccin", "centre")
                .order_by("-date_vaccination")
            )

            nb_doses = vaccs_enfant_qs.count()
            vaccs_types = (
                vaccs_enfant_qs
                .values("vaccin_id", "vaccin__nom")
                .distinct()
                .count()
            )

            # Prochain rappel enfant
            rappels_enfant_qs = vaccs_enfant_qs.filter(
                date_rappel__isnull=False,
                date_rappel__gte=today
            ).order_by("date_rappel")

            prochain_rappel_enfant = rappels_enfant_qs.first()

            # Statut calendrier enfant
            rappel_en_retard_enfant = vaccs_enfant_qs.filter(
                date_rappel__isnull=False,
                date_rappel__lt=today
            ).exists()

            if rappel_en_retard_enfant:
                statut_cal = "Rappels en retard"
                statut_cal_color = "red"
            elif prochain_rappel_enfant:
                statut_cal = "Rappels à venir"
                statut_cal_color = "amber"
            else:
                statut_cal = "Calendrier à jour"
                statut_cal_color = "emerald"

            enfants_data.append({
                "obj": enfant,
                "age": enfant.age,
                "nb_doses": nb_doses,
                "nb_vaccins": vaccs_types,
                "prochain_rappel": prochain_rappel_enfant,
                "statut_calendrier": statut_cal,
                "statut_calendrier_color": statut_cal_color,
                "centre": enfant.centre_actuel or enfant.centre,
            })
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

        # Vaccinations externes
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
        # 2) Vaccins uniques
        # ---------------------------------------------------------------------
        vaccins_uniques = (
            vaccinations_qs
            .values("vaccin_id", "vaccin__nom")
            .distinct()
        )

        # ---------------------------------------------------------------------
        # 3) Prochain rappel & rappels à venir
        # ---------------------------------------------------------------------
        rappels_qs = (
            vaccinations_qs
            .filter(date_rappel__isnull=False, date_rappel__gte=today)
            .order_by("date_rappel")
        )

        prochain_rappel = rappels_qs.first()

        rappels_prochains = []
        for v in rappels_qs[:10]:
            jours_restants = (v.date_rappel - today).days
            urgent = jours_restants <= 7
            rappels_prochains.append({
                "vaccin": v.vaccin,
                "dose": v.dose,
                "date": v.date_rappel,
                "jours_restants": jours_restants,
                "urgent": urgent,
            })

        # ---------------------------------------------------------------------
        # 4) Dernières vaccinations (cartes)
        # ---------------------------------------------------------------------
        derniers_vaccinations_qs = vaccinations_qs[:4]

        palette_couleurs = ["emerald", "sky", "amber", "violet"]
        palette_icones = [
            "fa-syringe",
            "fa-shield-virus",
            "fa-baby",
            "fa-notes-medical",
        ]

        derniers_vaccinations = []
        for idx, v in enumerate(derniers_vaccinations_qs):
            couleur = palette_couleurs[idx % len(palette_couleurs)]
            icone = palette_icones[idx % len(palette_icones)]

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
        # 5) Statut global calendrier vaccinal
        # ---------------------------------------------------------------------
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
        # ✅ 6) MAPI (effets indésirables)
        # ---------------------------------------------------------------------
        mapi_qs = Mapi.objects.filter(
            patient=patient,
            deleted_at__isnull=True,
        ).order_by("-date")

        nb_mapi = mapi_qs.count()
        derniers_mapi = mapi_qs[:3]

        # ---------------------------------------------------------------------
        # ✅ 7) Messages d’information globaux
        # ---------------------------------------------------------------------
        messages_info_qs = (
            Message.objects.filter(
                deleted_at__isnull=True,
                is_active=True,
            )
            .order_by("-created_at")[:5]
        )

        # ---------------------------------------------------------------------
        # ✅ 8) must_change_password
        # ---------------------------------------------------------------------
        must_change_password = patient.must_change_password

        # ---------------------------------------------------------------------
        # ✅ 9) Centre actuel
        # ---------------------------------------------------------------------
        centre_actuel = patient.centre_actuel or patient.centre

        # ---------------------------------------------------------------------
        # ✅ 10) Consultations du patient
        # ---------------------------------------------------------------------
        consultations_qs = (
            patient.consultations
            .filter(deleted_at__isnull=True)
            .order_by("-created_at")
        )
        consultations_count = consultations_qs.count()
        last_consultation = consultations_qs.first()

        # ---------------------------------------------------------------------
        # ✅ 11) Rendez-vous de vaccination pour ce patient
        # ---------------------------------------------------------------------
        rdv_patient_qs = RendezVousVaccination.objects.filter(
            patient=patient
        )

        rdv_futurs_qs = rdv_patient_qs.filter(
            date_heure__gte=now,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
        ).order_by("date_heure")

        rdv_today_qs = rdv_patient_qs.filter(
            date_heure__date=today,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
        )

        rdv_retard_qs = rdv_patient_qs.filter(
            date_heure__lt=now,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
        )

        rdv_prochain = rdv_futurs_qs.first()

        rdv_a_venir_count = rdv_futurs_qs.count()
        rdv_today_count = rdv_today_qs.count()
        rdv_retard_count = rdv_retard_qs.count()

        # ➕ stats RDV sur 12 derniers mois
        un_an = today - timedelta(days=365)
        rdv_12m = rdv_patient_qs.filter(date_heure__date__gte=un_an)
        rdv_12m_total = rdv_12m.count()
        rdv_12m_honores = rdv_12m.filter(statut=RendezVousStatut.HONORE).count()

        if rdv_12m_total > 0:
            taux_rdv_honores = round((rdv_12m_honores / rdv_12m_total) * 100, 1)
        else:
            taux_rdv_honores = 0

        rdv_stats_patient = {
            "total_12m": rdv_12m_total,
            "honores_12m": rdv_12m_honores,
            "taux_honores": taux_rdv_honores,
        }

        # ---------------------------------------------------------------------
        # ✅ 12) Vaccinations sur 12 derniers mois (pour mini-indicateur)
        # ---------------------------------------------------------------------
        vaccinations_12m_count = vaccinations_qs.filter(
            date_vaccination__gte=un_an
        ).count()

        # ---------------------------------------------------------------------
        # 13) Mise à jour du contexte
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

            # ➕ nouveaux indicateurs
            "consultations_count": consultations_count,
            "last_consultation": last_consultation,
            "rdv_prochain": rdv_prochain,
            "rdv_a_venir_count": rdv_a_venir_count,
            "rdv_today_count": rdv_today_count,
            "rdv_retard_count": rdv_retard_count,
            "rdv_stats_patient": rdv_stats_patient,
            "vaccinations_12m_count": vaccinations_12m_count,

            "enfants_suivis": enfants_data,

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


# -------------------------------------------------------------------
# Mixin commun : récupère le "patient" et un queryset de base optimisé
# -------------------------------------------------------------------
class PatientRdvMixin(LoginRequiredMixin):
    """
    Mixin pour centraliser :
    - la récupération du patient courant
    - un queryset de base optimisé
    """

    def get_patient(self):
        """
        IMPORTANT : on s'aligne sur ce qui marche déjà dans ta ListView,
        donc on renvoie self.request.user.
        Si plus tard tu veux basculer sur self.request.user.patient,
        tu n'auras qu'à changer ici.
        """
        return self.request.user

    def get_base_queryset(self):
        patient = self.get_patient()
        return (
            RendezVousVaccination.objects
            .filter(patient=patient)
            .select_related("centre", "service", "personnel_affecte")
        )


# -------------------------------------------------------------------
# Liste des rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationListView(PatientRdvMixin, ListView):
    model = RendezVousVaccination
    template_name = 'patient_space/rendez_vous/liste.html'
    context_object_name = 'rendez_vous'
    paginate_by = 10

    def get_queryset(self):
        qs = self.get_base_queryset()

        # --- filtres simples ---
        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        type_rdv = self.request.GET.get('type')
        if type_rdv:
            qs = qs.filter(type_rdv=type_rdv)

        # PEV (1 = PEV, 0 = hors PEV)
        pev = self.request.GET.get('pev')
        if pev == '1':
            qs = qs.filter(est_pev=True)
        elif pev == '0':
            qs = qs.filter(est_pev=False)

        # Priorité
        priorite = self.request.GET.get('priorite')
        if priorite in dict(PrioriteRendezVous.choices):
            qs = qs.filter(priorite=priorite)

        # Canal
        canal = self.request.GET.get('canal')
        if canal in dict(RendezVousCanal.choices):
            qs = qs.filter(canal_prise=canal)

        # Recherche texte (centre, motif)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(centre__nom__icontains=q) |
                Q(motif__icontains=q) |
                Q(commentaire__icontains=q)
            )

        # Tri
        tri = self.request.GET.get('tri', '-date_heure')
        if tri in ['date_heure', '-date_heure', 'statut', 'type_rdv', 'priorite']:
            qs = qs.order_by(tri)
        else:
            qs = qs.order_by('-date_heure')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = self.get_base_queryset()
        now = timezone.now()

        futurs_qs = base_qs.filter(
            date_heure__gte=now,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME]
        )
        passes_qs = base_qs.filter(date_heure__lt=now)

        context['stats'] = {
            'total': base_qs.count(),
            'planifies': base_qs.filter(statut=RendezVousStatut.PLANIFIE).count(),
            'confirmes': base_qs.filter(statut=RendezVousStatut.CONFIRME).count(),
            'honores': base_qs.filter(statut=RendezVousStatut.HONORE).count(),
            'absents': base_qs.filter(statut=RendezVousStatut.ABSENT).count(),
            'annules': base_qs.filter(statut=RendezVousStatut.ANNULE).count(),
            'a_venir': futurs_qs.count(),
            'passes': passes_qs.count(),
            'taux_honores': (
                base_qs.filter(statut=RendezVousStatut.HONORE).count() / base_qs.count() * 100
                if base_qs.count() > 0 else 0
            ),
            'prochain': futurs_qs.order_by('date_heure').first(),
        }

        context['types_rendezvous'] = RendezVousType.choices
        context['statuts_rendezvous'] = RendezVousStatut.choices
        context['priorites_rdv'] = PrioriteRendezVous.choices
        context['canaux_rdv'] = RendezVousCanal.choices

        context['filtre_actuel'] = {
            'statut': self.request.GET.get('statut', ''),
            'type': self.request.GET.get('type', ''),
            'tri': self.request.GET.get('tri', '-date_heure'),
            'pev': self.request.GET.get('pev', ''),
            'priorite': self.request.GET.get('priorite', ''),
            'canal': self.request.GET.get('canal', ''),
            'q': self.request.GET.get('q', ''),
        }
        context['patient'] = self.get_patient()
        return context

# -------------------------------------------------------------------
# Création de rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationCreateView(PatientRdvMixin, CreateView):
    model = RendezVousVaccination
    form_class = RendezVousVaccinationForm
    template_name = 'patient_space/rendez_vous/creer.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['patient'] = self.get_patient()
        return kwargs

    def form_valid(self, form):
        patient = self.get_patient()
        form.instance.patient = patient
        form.instance.canal_prise = RendezVousCanal.WEB

        # Vérifier la disponibilité du créneau (simple)
        date_rdv = form.instance.date_heure
        centre = form.instance.centre

        conflits = RendezVousVaccination.objects.filter(
            centre=centre,
            date_heure=date_rdv,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
        )

        if conflits.exists():
            form.add_error(
                'date_heure',
                "Ce créneau n'est plus disponible. Veuillez choisir un autre horaire."
            )
            return self.form_invalid(form)

        response = super().form_valid(form)

        messages.success(
            self.request,
            f"Rendez-vous planifié pour le {form.instance.date_heure.strftime('%d/%m/%Y à %H:%M')}"
        )
        # TODO: Notification (SMS / e-mail / push)
        return response

    def get_success_url(self):
        return reverse_lazy('patient_rendez_vous_liste')


# -------------------------------------------------------------------
# Détail d’un rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationDetailView(PatientRdvMixin, DetailView):
    model = RendezVousVaccination
    template_name = 'patient_space/rendez_vous/detail.html'
    context_object_name = 'rendez_vous'

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient'] = self.get_patient()
        return context


# -------------------------------------------------------------------
# Modification d’un rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationUpdateView(PatientRdvMixin, UpdateView):
    model = RendezVousVaccination
    form_class = RendezVousVaccinationForm
    template_name = 'patient_space/rendez_vous/modifier.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['patient'] = self.get_patient()
        return kwargs

    def get_queryset(self):
        now = timezone.now()
        # On autorise la modif uniquement pour RDV futurs planifiés/confirmés (avec marge de 2h)
        return self.get_base_queryset().filter(
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
            date_heure__gt=now + timezone.timedelta(hours=2),
        )

    def form_valid(self, form):
        messages.success(self.request, "Rendez-vous modifié avec succès.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('patient_rendez_vous_detail', kwargs={'pk': self.object.pk})


# -------------------------------------------------------------------
# Annulation d’un rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationAnnulerView(PatientRdvMixin, View):
    def get_object(self, pk):
        return get_object_or_404(
            self.get_base_queryset(),
            pk=pk,
        )

    def get(self, request, pk):
        rdv = self.get_object(pk)

        if not rdv.can_be_cancelled or not rdv.is_future:
            messages.error(request, "Ce rendez-vous ne peut plus être annulé.")
            return redirect('patient_rendez_vous_liste')

        form = AnnulationRendezVousForm()
        return self.render_response(request, rdv, form)

    def post(self, request, pk):
        rdv = self.get_object(pk)
        form = AnnulationRendezVousForm(request.POST)

        if form.is_valid() and rdv.can_be_cancelled and rdv.is_future:
            rdv.marquer_annule(motif=form.cleaned_data['motif_annulation'], user=None)
            messages.success(request, "Rendez-vous annulé avec succès.")
            # TODO: Notification d'annulation
            return redirect('patient_rendez_vous_liste')

        return self.render_response(request, rdv, form)

    def render_response(self, request, rendez_vous, form):
        return render(
            request,
            'patient_space/rendez_vous/annuler.html',
            {
                'rendez_vous': rendez_vous,
                'form': form,
                'patient': self.get_patient(),
            }
        )


# -------------------------------------------------------------------
# Confirmation d’un rendez-vous
# -------------------------------------------------------------------
class RendezVousVaccinationConfirmerView(PatientRdvMixin, View):
    def post(self, request, pk):
        rdv = get_object_or_404(
            self.get_base_queryset(),
            pk=pk,
            statut=RendezVousStatut.PLANIFIE,
        )

        rdv.marquer_confirme(user=None)
        messages.success(request, "Rendez-vous confirmé avec succès.")
        return redirect('patient_rendez_vous_liste')


# -------------------------------------------------------------------
# Vue calendrier (template)
# -------------------------------------------------------------------
class RendezVousVaccinationCalendarView(PatientRdvMixin, TemplateView):
    template_name = "patient_space/rendez_vous/calendrier.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.get_patient()

        context["rendez_vous_prochains"] = (
            self.get_base_queryset()
            .filter(date_heure__gte=timezone.now())
            .order_by("date_heure")[:10]
        )
        context["patient"] = patient
        return context


# -------------------------------------------------------------------
# API events pour FullCalendar
# -------------------------------------------------------------------
class RendezVousVaccinationEventsView(PatientRdvMixin, View):
    """
    API JSON pour FullCalendar (events).
    FullCalendar appelle GET ?start=...&end=...
    """

    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")

        if not start or not end:
            return JsonResponse([], safe=False)

        # parse_datetime gère les formats ISO avec ou sans "Z"
        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)

        if not start_dt or not end_dt:
            return JsonResponse([], safe=False)

        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)

        qs = self.get_base_queryset().filter(
            date_heure__range=[start_dt, end_dt],
        )

        events = []
        for rdv in qs:
            fin = rdv.date_heure + timedelta(
                minutes=rdv.duree_minutes or 15
            )
            events.append({
                "id": rdv.id,
                "title": f"RDV {rdv.get_type_rdv_display()}",
                "start": rdv.date_heure.isoformat(),
                "end": fin.isoformat(),
                "color": self.get_event_color(rdv.statut),
                "textColor": "white",
                "extendedProps": {
                    "statut": rdv.get_statut_display(),
                    "centre": getattr(rdv.centre, "name", None) or getattr(rdv.centre, "nom", ""),
                    "type": rdv.type_rdv,
                },
            })

        return JsonResponse(events, safe=False)

    def get_event_color(self, statut):
        colors = {
            RendezVousStatut.PLANIFIE: "#3b82f6",  # bleu
            RendezVousStatut.CONFIRME: "#10b981",  # vert
            RendezVousStatut.HONORE: "#6b7280",  # gris
            RendezVousStatut.ANNULE: "#ef4444",  # rouge
            RendezVousStatut.REPORTE: "#f59e0b",  # amber
            RendezVousStatut.ABSENT: "#dc2626",  # rouge foncé
        }
        return colors.get(statut, "#6b7280")


# -------------------------------------------------------------------
# Stats JSON (pour dashboards futurs)
# -------------------------------------------------------------------
class RendezVousVaccinationStatsView(PatientRdvMixin, View):
    def get(self, request):
        base_qs = self.get_base_queryset()

        stats = base_qs.aggregate(
            total=Count('id'),
            honores=Count('id', filter=Q(statut=RendezVousStatut.HONORE)),
            annules=Count('id', filter=Q(statut=RendezVousStatut.ANNULE)),
            absents=Count('id', filter=Q(statut=RendezVousStatut.ABSENT)),
        )

        types_stats = (
            base_qs.values('type_rdv')
            .annotate(
                count=Count('id'),
                honores=Count('id', filter=Q(statut=RendezVousStatut.HONORE)),
            )
            .order_by('type_rdv')
        )

        return JsonResponse(
            {
                'stats_generales': stats,
                'par_type': list(types_stats),
            }
        )
