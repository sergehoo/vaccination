import base64
import datetime
import io
import tempfile
from collections import defaultdict

import qrcode
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import models
from django.db.models import Q, Prefetch, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string, get_template
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
from weasyprint import HTML
from xhtml2pdf import pisa

from inhp.backends import StaffOnlyMixin
from inhp.forms import VaccinationFilterForm, VaccinationForm
from inhp.models import Patient, Vaccination, Maladie, Mapi, VaccineExt, Consultation, AccessLevel, Role, Vaccin, \
    LotVaccin, CentreVaccination, Utilisateur
from django.utils.translation import gettext as _


class LandingView(TemplateView):
    template_name = "publiq/landing.html"


class HomePageView(StaffOnlyMixin, LoginRequiredMixin, TemplateView):
    login_url = '/accounts/login/'
    # form_class = LoginForm
    template_name = "pages/home.html"


# def patient_login_view(request):
#     if request.method == 'POST':
#         code_patient = request.POST.get('code_patient')
#         telephone = request.POST.get('telephone')
#         backend = PatientAuthBackend()
#         user = backend.authenticate(request, code_patient=code_patient, telephone=telephone)
#         if user:
#             login(request, user, backend='inhp.backends.PatientAuthBackend')
#             return redirect('patient_dashboard')  # Vue spéciale patient
#         else:
#             messages.error(request, 'Code patient ou téléphone incorrect.')
#     return render(request, 'patient_space/patient_login.html')


@login_required
def patient_dashboard(request):
    return render(request, 'patient_space/patient_dashboard.html', {'patient': request.user})


@login_required
def mes_vaccins(request):
    patient = request.user
    vaccinations = Vaccination.objects.filter(patient=patient).select_related(
        'vaccin', 'vaccin__maladie', 'centre'
    ).order_by('vaccin__maladie__nom', 'date_vaccination')

    maladies_vaccins = {}
    for vacc in vaccinations:
        maladie = vacc.vaccin.maladie
        if maladie not in maladies_vaccins:
            maladies_vaccins[maladie] = {
                'maladie': maladie,
                'vaccinations': [],
                'doses_completes': False
            }

        maladies_vaccins[maladie]['vaccinations'].append(vacc)
        vaccin = vacc.vaccin
        doses_recues = len([v for v in maladies_vaccins[maladie]['vaccinations']
                            if v.vaccin == vaccin])
        maladies_vaccins[maladie]['doses_completes'] = (doses_recues >= vaccin.doses_requises)

    if request.GET.get('download') and request.GET.get('maladie_id'):
        maladie_id = request.GET.get('maladie_id')
        maladie = next((m for m in maladies_vaccins.keys() if m.id == int(maladie_id)), None)

        if maladie and maladies_vaccins[maladie]['doses_completes']:
            return generate_pdf_certificat(request, patient, maladie, maladies_vaccins[maladie])

    return render(request, 'patient_space/mes_vaccins.html', {
        'maladies_vaccins': maladies_vaccins.values()
    })


def verifier_certificat(request, patient_id, maladie_id):
    patient = get_object_or_404(Patient, id=patient_id)
    maladie = get_object_or_404(Maladie, id=maladie_id)

    vaccinations = Vaccination.objects.filter(
        patient=patient,
        vaccin__maladie=maladie
    ).select_related("vaccin", "lot", "centre")

    return render(request, "patient_space/verifier_certificat.html", {
        'patient': patient,
        'maladie': maladie,
        'vaccinations': vaccinations
    })


def generate_qr_code(data):
    qr = qrcode.make(data)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def generate_certificat_pdf_response(request, patient, maladie, vaccinations_data):
    template_path = 'patient_space/certificat_vaccination.html'
    url_certificat = request.build_absolute_uri(
        reverse('verifier_certificat', kwargs={
            'patient_id': patient.id,
            'maladie_id': maladie.id
        })
    )
    qr_code_data = generate_qr_code(url_certificat)

    context = {
        'patient': patient,
        'maladie': maladie,
        'vaccinations': vaccinations_data['vaccinations'],
        'date_emission': timezone.now().date(),
        'mshplogo': request.build_absolute_uri('/static/images/logo/mshp.png'),
        'inhplogo': request.build_absolute_uri('/static/images/logo/logo-001_0.png'),
        'rcilogo': request.build_absolute_uri('/static/images/logo/rci.jpeg'),
        'qr_code_data': qr_code_data,
        'reference': f'{timezone.now().date()}*{patient.id}*{patient.code_patient}*{maladie.id}',

    }

    response = HttpResponse(content_type='application/pdf')
    response[
        'Content-Disposition'] = f'attachment; filename="certificat_vaccination_{maladie.nom}_{patient.code_patient}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    # Création du PDF
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Erreur lors de la génération du PDF', status=500)

    return response


def generate_pdf_certificat(request, maladie_id):
    patient = request.user
    maladie = get_object_or_404(Maladie, id=maladie_id)

    vaccinations_data = {
        "vaccinations": Vaccination.objects.filter(
            patient=patient,
            vaccin__maladie=maladie
        ).select_related("vaccin", "lot", "centre").order_by("date_vaccination")
    }

    return generate_certificat_pdf_response(request, patient, maladie, vaccinations_data)


#------------------------------------------------------For Bakend Part------------------------


class DashboardView(StaffOnlyMixin, TemplateView):
    login_url = '/accounts/login/'
    template_name = "administration/dashboard.html"

    def _apply_scope(self, queryset, user, field_prefix="centre"):
        """
        Applique le scope (centre / district / région / pôle / national)
        sur un queryset qui possède un lien vers centre/district/région/pôle.

        Field_prefix : nom du champ de base, ex : "centre" ou "centre__district"
        """
        if not isinstance(user, Utilisateur):
            return queryset

        # Exemples:
        # field_prefix="centre"        -> centre=...
        # field_prefix="centre__district" -> centre__district=...
        # etc.
        if user.access_level == AccessLevel.CENTRE and user.centre_id:
            return queryset.filter(**{f"{field_prefix}": user.centre})
        if user.access_level == AccessLevel.DISTRICT and user.district_id:
            return queryset.filter(**{f"{field_prefix}__district": user.district})
        if user.access_level == AccessLevel.REGION and user.region_id:
            return queryset.filter(**{f"{field_prefix}__district__region": user.region})
        if user.access_level == AccessLevel.POLE and user.pole_id:
            return queryset.filter(**{f"{field_prefix}__district__region__poles": user.pole})

        # Niveau national > pas de restriction supplémentaire
        return queryset

    def _get_scope_label(self, user):
        if not isinstance(user, Utilisateur):
            return "National"

        if user.access_level == AccessLevel.CENTRE and user.centre:
            return f"Centre : {user.centre.name}"
        if user.access_level == AccessLevel.DISTRICT and user.district:
            return f"District : {user.district.nom}"
        if user.access_level == AccessLevel.REGION and user.region:
            return f"Région : {user.region.name}"
        if user.access_level == AccessLevel.POLE and user.pole:
            return f"Pôle : {user.pole.name}"
        return "National"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = datetime.date.today()
        now = timezone.now()

        # ---------------------------------------------------------------------
        # 1) VACCINATIONS (scopées)
        # ---------------------------------------------------------------------
        vaccinations_qs = Vaccination.objects.all().select_related("centre", "vaccin", "centre__district__region")

        vaccinations_qs = self._apply_scope(vaccinations_qs, user, field_prefix="centre")

        # Total doses (toutes périodes)
        total_doses = vaccinations_qs.count()

        # Doses du jour (pour le hero)
        total_doses_today = vaccinations_qs.filter(date_vaccination=today).count()

        # 30 derniers jours (graph + stats)
        start_30 = today - datetime.timedelta(days=29)
        vaccinations_30_qs = vaccinations_qs.filter(date_vaccination__gte=start_30)

        # Groupement par jour pour Chart.js
        by_day = (
            vaccinations_30_qs
            .values("date_vaccination")
            .annotate(total=Count("id"))
            .order_by("date_vaccination")
        )

        chart_labels = []
        chart_data = []
        for row in by_day:
            chart_labels.append(row["date_vaccination"].strftime("%d/%m"))
            chart_data.append(row["total"])

        # ---------------------------------------------------------------------
        # 2) Couverture "nationale" (ou scope)
        #    approche simple : patients vaccinés / patients enregistrés
        # ---------------------------------------------------------------------
        patients_qs = Patient.objects.all()
        patients_qs = self._apply_scope(patients_qs, user, field_prefix="centre")

        total_patients = patients_qs.count()

        patients_vaccines = (
            patients_qs.filter(historique_vaccinations__in=vaccinations_qs)
            .distinct()
            .count()
        )

        couverture = 0.0
        if total_patients > 0:
            couverture = round((patients_vaccines / total_patients) * 100, 1)

        # ---------------------------------------------------------------------
        # 3) Centres actifs + alertes stock
        # ---------------------------------------------------------------------
        centres_qs = CentreVaccination.objects.all().select_related("district__region")

        centres_qs = self._apply_scope(centres_qs, user, field_prefix="id")

        centres_actifs = centres_qs.count()

        # Lots pour détection des stocks critiques (< 7 jours / quantite basse)
        lots_qs = LotVaccin.objects.filter(
            centre__in=centres_qs,
            quantite_disponible__isnull=False,
        ).select_related("centre__district__region", "vaccin")

        centres_stock_alertes = []
        seuil_quantite = 100  # à ajuster
        jours_limite = 7  # à ajuster

        for lot in lots_qs:
            statut = None
            nb_jours = None

            if lot.date_expiration:
                nb_jours = (lot.date_expiration - today).days

            # Règles simplifiées
            if lot.quantite_disponible <= 0 or (nb_jours is not None and nb_jours <= 0):
                statut = "critique"
            elif lot.quantite_disponible <= seuil_quantite or (nb_jours is not None and nb_jours <= jours_limite):
                statut = "alerte"

            if statut:
                centres_stock_alertes.append({
                    "centre": lot.centre,
                    "region": lot.centre.district.region if lot.centre and lot.centre.district and lot.centre.district.region else None,
                    "vaccin": lot.vaccin,
                    "quantite": lot.quantite_disponible,
                    "jours_restants": nb_jours,
                    "statut": statut,
                })

        # on limite l'affichage à 10 lignes
        centres_stock_alertes = centres_stock_alertes[:10]

        # ---------------------------------------------------------------------
        # 4) Incidents / MAPI
        # ---------------------------------------------------------------------
        mapi_qs = Mapi.objects.filter(
            vaccination__in=vaccinations_qs,
        ).select_related("centre", "vaccination", "patient")

        incidents_total = mapi_qs.count()
        incidents_24h = mapi_qs.filter(date__gte=now - datetime.timedelta(hours=24)).count()
        incidents_30j = mapi_qs.filter(date__gte=now - datetime.timedelta(days=30)).count()

        # ---------------------------------------------------------------------
        # 5) Contexte pour le hero + infos
        # ---------------------------------------------------------------------
        scope_label = self._get_scope_label(user)

        ctx.update({
            "scope_label": scope_label,
            "last_update": now,
            "total_doses": total_doses,
            "total_doses_today": total_doses_today,
            "couverture": couverture,
            "total_patients": total_patients,
            "patients_vaccines": patients_vaccines,
            "centres_actifs": centres_actifs,
            "centres_stock_alertes": centres_stock_alertes,
            "incidents_total": incidents_total,
            "incidents_24h": incidents_24h,
            "incidents_30j": incidents_30j,
            # Données pour le graph
            "chart_vaccinations_labels": chart_labels,
            "chart_vaccinations_data": chart_data,
        })
        return ctx


#----------------============================== Patiens ========================== -----------------------------------
class PatientListView(StaffOnlyMixin, LoginRequiredMixin, ListView):
    model = Patient
    template_name = 'administration/patients_list.html'
    context_object_name = 'patients'
    paginate_by = 10
    # ordering = ['nom', 'prenoms', '-created_at', ]
    ordering = ['nom', 'prenoms']

    def get_queryset(self):
        queryset = super().get_queryset().all()

        q = self.request.GET.get('q')
        statut = self.request.GET.get('statut')
        centre = self.request.GET.get('centre')

        if q:
            queryset = queryset.filter(Q(nom__icontains=q) | Q(prenoms__icontains=q) | Q(telephone1__icontains=q))

        if statut:
            queryset = queryset.filter(statut=statut)

        if centre:
            queryset = queryset.filter(centre_id=centre)

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('administration/admin/partials/patients_table_partial.html', context,
                                    request=self.request)
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = now()
        seven_days_ago = today - datetime.timedelta(days=7)

        all_patients = Patient.objects.all()
        total_patients = all_patients.count()
        active_patients = all_patients.filter(is_active=True).count()
        inactive_patients = all_patients.filter(is_active=False).count()
        new_patients = all_patients.filter(created_at__gte=seven_days_ago).count()

        # Éviter la division par zéro
        active_percentage = (active_patients / total_patients * 100) if total_patients else 0
        inactive_percentage = (inactive_patients / total_patients * 100) if total_patients else 0

        context.update({
            'total_patients': total_patients,
            'active_patients': active_patients,
            'inactive_patients': inactive_patients,
            'new_patients': new_patients,
            'stats': {
                'active_percentage': active_percentage,
                'inactive_percentage': inactive_percentage,
            }
        })
        return context


class PatientVaccinationCarnetPDFView(StaffOnlyMixin, LoginRequiredMixin, View):
    """
    Génère le carnet de vaccination complet d'un patient en PDF.
    """

    def get(self, request, code_patient, *args, **kwargs):
        patient = get_object_or_404(
            Patient.objects.all(),
            code_patient=code_patient,
        )

        # Reprise des mêmes jeux de données que PatientDetailView
        vaccinations = (
            Vaccination.objects
            .filter(patient=patient)
            .select_related('centre', 'vaccin', 'vaccin__maladie', 'lot', 'created_by')
            .order_by('date_vaccination', 'dose')
        )

        vaccines_ext = (
            VaccineExt.objects
            .filter(patient=patient)
            .select_related('vaccin', 'utilisateur')
            .order_by('date', '-created_at')
        )

        mapis = (
            Mapi.objects
            .filter(patient=patient)
            .select_related('centre', 'vaccination__vaccin', 'utilisateur')
            .order_by('-date', '-created_at')
        )

        consultations = (
            Consultation.objects
            .filter(patient=patient)
            .select_related('centre', 'maladie', 'utilisateur')
            .order_by('-created_at')
        )

        # ------------------ Génération du QR code ------------------
        # Tu peux mettre ici ce que tu veux encoder : URL de vérification,
        # payload signé, etc. Pour l'instant : code patient + date.
        verification_payload = (
            f"CARNET|{patient.code_patient}|"
            f"{patient.nom} {patient.prenoms}|"
            f"{timezone.now().date().isoformat()}"
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,  # taille raisonnable pour un PDF A4
            border=2,
        )
        qr.add_data(verification_payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        qr_data_uri = f"data:image/png;base64,{qr_base64}"
        # -----------------------------------------------------------

        context = {
            "patient": patient,
            "vaccinations": vaccinations,
            "vaccines_ext": vaccines_ext,
            "mapis": mapis,
            "consultations": consultations,
            "today": timezone.now().date(),
            "qr_code_data": qr_data_uri,
        }

        # 1) On rend le template HTML
        html_string = render_to_string(
            "administration/vaccinations/carnet_vaccination_pdf.html",
            context
        )

        if HTML is None:
            # fallback : renvoyer juste l’HTML si WeasyPrint n’est pas installé
            return HttpResponse(html_string)

        # 2) On génère le PDF avec WeasyPrint
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

        # 3) On renvoie la réponse HTTP PDF
        filename = f"Carnet_vaccinal_{patient.code_patient}.pdf"
        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PatientDetailView(StaffOnlyMixin, LoginRequiredMixin, DetailView):
    model = Patient
    template_name = 'administration/patient_detail.html'
    context_object_name = 'patient'
    slug_field = 'code_patient'
    slug_url_kwarg = 'code_patient'

    def get_queryset(self):
        """
        On restreint aux patients non supprimés,
        et on optimise un peu les relations principales.
        """
        return (
            Patient.objects
            .select_related('centre', 'centre_actuel', 'created_by')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object

        # Historique vaccinal interne
        vaccinations = (
            Vaccination.objects
            .filter(patient=patient)
            .select_related('centre', 'vaccin', 'lot', 'created_by')
            .order_by('-date_vaccination', '-created_at')
        )

        # Vaccins réalisés à l’étranger
        vaccines_ext = (
            VaccineExt.objects
            .filter(patient=patient)
            .select_related('vaccin', 'utilisateur')
            .order_by('-date', '-created_at')
        )

        # Consultations liées
        consultations = (
            Consultation.objects
            .filter(patient=patient)
            .select_related('centre', 'maladie', 'utilisateur')
            .order_by('-created_at')
        )

        # MAPI / incidents post-vaccinaux
        mapis = (
            Mapi.objects
            .filter(patient=patient)
            .select_related('centre', 'vaccination__vaccin', 'utilisateur')
            .order_by('-date', '-created_at')
        )

        context.update({
            "vaccinations": vaccinations,
            "vaccines_ext": vaccines_ext,
            "consultations": consultations,
            "mapis": mapis,
            # Petites stats récap si tu veux les exploiter
            "vaccinations_count": vaccinations.count(),
            "vaccines_ext_count": vaccines_ext.count(),
            "consultations_count": consultations.count(),
            "mapis_count": mapis.count(),
        })
        return context


class PatientCreateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Patient
    template_name = 'patient/form.html'
    fields = [
        'nom', 'prenoms', 'date_naissance', 'sexe',
        'email', 'telephone1', 'telephone2',
        'situation_matrimoniale', 'nombre_enfant',
        'nationalite', 'type_piece', 'num_piece',
        'commune', 'quartier', 'niveau_instruction',
        'profession', 'consentement_parental',
        'centre', 'centre_actuel'
    ]
    permission_required = 'patients.add_patient'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('patient-detail', kwargs={'code_patient': self.object.code_patient})


class PatientUpdateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Patient
    template_name = 'patient/form.html'
    fields = [
        'nom', 'prenoms', 'date_naissance', 'sexe',
        'email', 'telephone1', 'telephone2',
        'situation_matrimoniale', 'nombre_enfant',
        'nationalite', 'type_piece', 'num_piece',
        'commune', 'quartier', 'niveau_instruction',
        'profession', 'consentement_parental',
        'statut', 'centre', 'centre_actuel'
    ]
    permission_required = 'patients.change_patient'
    slug_field = 'code_patient'
    slug_url_kwarg = 'code_patient'

    def get_success_url(self):
        return reverse_lazy('patient-detail', kwargs={'code_patient': self.object.code_patient})


class PatientDeleteView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Patient
    template_name = 'patient/confirm_delete.html'
    permission_required = 'patients.delete_patient'
    slug_field = 'code_patient'
    slug_url_kwarg = 'code_patient'
    success_url = reverse_lazy('patient-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted_at = timezone.now()
        self.object.is_active = False
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


#--------====================== Vaccination ================== -------
class VaccinationListView(StaffOnlyMixin, LoginRequiredMixin, TemplateView):
    template_name = 'administration/vaccinations/vaccination_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Formulaire uniquement pour les champs (patient, centre, vaccin, dates)
        context['filter_form'] = VaccinationFilterForm(self.request.GET or None)
        # Le JS mettra ces valeurs à jour à partir de l'API
        context['total_vaccinations'] = 0
        context['rappels_prochains'] = 0
        context['rappels_manques'] = 0
        return context


class VaccinationCreateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Vaccination
    form_class = VaccinationForm
    template_name = 'administration/vaccinations/vaccination_form.html'
    permission_required = 'vaccinations.add_vaccination'
    success_url = reverse_lazy('vaccination_list')

    def form_valid(self, form):
        # Définir l'utilisateur connecté comme créateur
        form.instance.created_by = self.request.user

        # Calculer automatiquement la date de rappel si non spécifiée
        if not form.instance.date_rappel and form.instance.vaccin:
            form.instance.date_rappel = form.instance.calculer_date_rappel()

        response = super().form_valid(form)

        # Mettre à jour le stock du lot si un lot est sélectionné
        if self.object.lot and self.object.lot.stock > 0:
            self.object.lot.stock -= 1
            self.object.lot.save()

        return response


class VaccinationDetailView(StaffOnlyMixin, LoginRequiredMixin, DetailView):
    model = Vaccination
    template_name = 'administration/vaccinations/vaccination_detail.html'
    context_object_name = 'vaccination'

    def get_queryset(self):
        # On optimise juste les FK directs, sans prefetch foireux
        return (
            Vaccination.objects
            .select_related(
                'patient',
                'centre',
                'vaccin',
                'vaccin__maladie',
                'lot',
                'created_by',
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vaccination = self.object

        # 🔹 Patient
        context['patient'] = vaccination.patient

        # 🔹 Historique des doses pour ce même vaccin / ce patient
        context['historique_vaccins'] = (
            Vaccination.objects
            .filter(
                patient=vaccination.patient,
                vaccin=vaccination.vaccin,

            )
            .select_related('centre', 'lot')
            .order_by('dose')
        )

        # 🔹 Dernières vaccinations du patient (tous vaccins)
        context['toutes_vaccinations'] = (
            Vaccination.objects
            .filter(
                patient=vaccination.patient,

            )
            .select_related('vaccin', 'centre', 'lot')
            .order_by('-date_vaccination')[:10]
        )

        # 🔹 Consultations liées à la maladie du vaccin
        maladie = getattr(vaccination.vaccin, 'maladie', None)
        if maladie:
            consultations_qs = (
                Consultation.objects
                .filter(
                    patient=vaccination.patient,
                    maladie=maladie,

                )
                .select_related('utilisateur', 'centre')
                .order_by('-created_at')[:5]
            )
        else:
            consultations_qs = Consultation.objects.none()

        context['consultations'] = consultations_qs

        # 🔹 Effets secondaires (MAPIs) liés à cette vaccination
        context['effets_secondaires'] = (
            Mapi.objects
            .filter(
                vaccination=vaccination

            )
            .select_related('utilisateur')
            .order_by('-created_at')
        )

        # 🔹 Statistiques de la vaccination
        context['stats'] = self.calculer_statistiques(vaccination)

        return context

    def calculer_statistiques(self, vaccination):
        """Calcule les statistiques pour cette vaccination"""
        # Vaccinations similaires (même vaccin, même centre)
        vaccinations_similaires = Vaccination.objects.filter(
            vaccin=vaccination.vaccin,
            centre=vaccination.centre
        )

        total_vaccin_centre = vaccinations_similaires.count()

        # Prochain rappel si applicable
        prochain_rappel = None
        if (
                vaccination.vaccin
                and vaccination.vaccin.besoin_rappel
                and vaccination.vaccin.doses_requises is not None
                and vaccination.vaccin.doses_requises > vaccination.dose
        ):
            prochain_rappel = vaccination.calculer_date_rappel()

        return {
            'total_vaccin_centre': total_vaccin_centre,
            'prochain_rappel': prochain_rappel,
            'jours_ecoules': (timezone.now().date() - vaccination.date_vaccination).days,
            'doses_restantes': (
                vaccination.vaccin.doses_requises - vaccination.dose
                if vaccination.vaccin and vaccination.vaccin.doses_requises is not None
                else None
            ),
        }


class VaccinationCertificatPDFView(StaffOnlyMixin, LoginRequiredMixin, View):
    """
    Génère un certificat de vaccination en PDF pour une vaccination donnée.
    """

    def get(self, request, pk, *args, **kwargs):
        vaccination = get_object_or_404(
            Vaccination,
            pk=pk,
        )

        patient = vaccination.patient
        centre = vaccination.centre

        # Contenu encodé dans le QR (à adapter : URL de vérification, résumé, etc.)
        qr_content = (
            f"Certificat de vaccination\n"
            f"Patient: {patient.nom} {patient.prenoms} ({patient.code_patient})\n"
            f"Vaccin: {vaccination.vaccin.nom if vaccination.vaccin else ''}\n"
            f"Dose: {vaccination.dose}\n"
            f"Date: {vaccination.date_vaccination}\n"
            f"Centre: {centre.name}\n"
        )

        # Génération du QR code en mémoire
        qr = qrcode.QRCode(
            version=1,
            box_size=4,
            border=2,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        qr_data_uri = f"data:image/png;base64,{qr_base64}"

        template = get_template('administration/vaccinations/certificat_vaccination_pdf.html')

        context = {
            'vaccination': vaccination,
            'patient': vaccination.patient,
            'centre': vaccination.centre,
            'today': timezone.now().date(),
            "qr_code_data": qr_data_uri,
        }

        html_string = template.render(context, request=request)

        response = HttpResponse(content_type='application/pdf')
        filename = f"certificat_vaccination_{vaccination.patient.code_patient}_{vaccination.pk}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # base_url obligatoire pour que les assets (logo, css) soient résolus correctement
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(target=response)

        return response


class VaccinationUpdateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Vaccination
    form_class = VaccinationForm
    template_name = 'administration/vaccinations/vaccination_form.html'
    permission_required = 'vaccinations.change_vaccination'

    def get_success_url(self):
        return reverse_lazy('vaccination_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # Sauvegarder l'ancien lot pour gestion du stock
        old_lot = None
        if self.object.lot:
            old_lot = self.object.lot

        response = super().form_valid(form)

        # Gérer la mise à jour du stock
        if old_lot and old_lot != self.object.lot:
            # Réapprovisionner l'ancien lot
            old_lot.stock += 1
            old_lot.save()

            # Déduire le nouveau lot
            if self.object.lot and self.object.lot.stock > 0:
                self.object.lot.stock -= 1
                self.object.lot.save()

        return response


class VaccinationDeleteView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Vaccination
    template_name = 'administration/administration/vaccinations/vaccination_confirm_delete.html'
    permission_required = 'vaccinations.delete_vaccination'
    success_url = reverse_lazy('vaccination_list')

    def form_valid(self, form):
        # Soft delete au lieu de suppression réelle
        self.object.deleted_at = timezone.now()
        self.object.save()
        return super().form_valid(form)


class VaccinationsRappelListView(StaffOnlyMixin, LoginRequiredMixin, ListView):
    model = Vaccination
    template_name = 'administration/administration/vaccinations/vaccinations_rappel.html'
    context_object_name = 'vaccinations_rappel'

    def get_queryset(self):
        # Vaccinations avec rappel dans les 30 prochains jours
        date_limit = timezone.now().date() + timezone.timedelta(days=30)
        return Vaccination.objects.filter(

            date_rappel__isnull=False,
            date_rappel__gte=timezone.now().date(),
            date_rappel__lte=date_limit
        ).order_by('date_rappel')


#----------------============================== Mapi  ========================== -----------------------------------
class MapiListView(StaffOnlyMixin, LoginRequiredMixin, ListView):
    model = Mapi
    template_name = 'mapi/list.html'
    context_object_name = 'mapis'
    paginate_by = 20
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset().all()
        # Filtrage par patient si besoin
        if 'patient_id' in self.kwargs:
            queryset = queryset.filter(patient__code_patient=self.kwargs['patient_id'])
        return queryset


class MapiDetailView(StaffOnlyMixin, LoginRequiredMixin, DetailView):
    model = Mapi
    template_name = 'mapi/detail.html'
    context_object_name = 'mapi'


class MapiCreateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Mapi
    template_name = 'mapi/form.html'
    fields = ['symptome', 'commentaire', 'date', 'patient', 'centre', 'vaccination']
    permission_required = 'patients.add_mapi'

    def get_initial(self):
        initial = super().get_initial()
        if 'patient_id' in self.kwargs:
            initial['patient'] = Patient.objects.get(code_patient=self.kwargs['patient_id'])
        return initial

    def form_valid(self, form):
        form.instance.utilisateur = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('mapi-detail', kwargs={'pk': self.object.pk})


class MapiUpdateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Mapi
    template_name = 'mapi/form.html'
    fields = ['symptome', 'commentaire', 'date', 'patient', 'centre', 'vaccination']
    permission_required = 'patients.change_mapi'

    def get_success_url(self):
        return reverse_lazy('mapi-detail', kwargs={'pk': self.object.pk})


class MapiDeleteView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Mapi
    template_name = 'mapi/confirm_delete.html'
    permission_required = 'patients.delete_mapi'
    success_url = reverse_lazy('mapi-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted_at = timezone.now()
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


#----------------============================== Vaccin exterieur  ========================== -----------------------------------


class VaccineExtListView(StaffOnlyMixin, LoginRequiredMixin, ListView):
    model = VaccineExt
    template_name = 'vaccine_ext/list.html'
    context_object_name = 'vaccine_exts'
    paginate_by = 20
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset().all()
        if 'patient_id' in self.kwargs:
            queryset = queryset.filter(patient__code_patient=self.kwargs['patient_id'])
        return queryset


class VaccineExtDetailView(StaffOnlyMixin, LoginRequiredMixin, DetailView):
    model = VaccineExt
    template_name = 'vaccine_ext/detail.html'
    context_object_name = 'vaccine_ext'


class VaccineExtCreateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = VaccineExt
    template_name = 'vaccine_ext/form.html'
    fields = ['pays', 'ville', 'numero_dose', 'lot', 'patient', 'vaccin', 'date']
    permission_required = 'patients.add_vaccineext'

    def get_initial(self):
        initial = super().get_initial()
        if 'patient_id' in self.kwargs:
            patient = Patient.objects.get(code_patient=self.kwargs['patient_id'])
            initial['patient'] = patient
            initial['code_patient'] = patient.code_patient
        return initial

    def form_valid(self, form):
        form.instance.utilisateur = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('vaccine-ext-detail', kwargs={'pk': self.object.pk})


class VaccineExtUpdateView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = VaccineExt
    template_name = 'vaccine_ext/form.html'
    fields = ['pays', 'ville', 'numero_dose', 'lot', 'patient', 'vaccin', 'date']
    permission_required = 'patients.change_vaccineext'

    def get_success_url(self):
        return reverse_lazy('vaccine-ext-detail', kwargs={'pk': self.object.pk})


class VaccineExtDeleteView(StaffOnlyMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = VaccineExt
    template_name = 'vaccine_ext/confirm_delete.html'
    permission_required = 'patients.delete_vaccineext'
    success_url = reverse_lazy('vaccine-ext-list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.deleted_at = timezone.now()
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

#----------------============================== Vaccin exterieur  ========================== -----------------------------------
