import base64
import datetime
import io
import tempfile
from collections import defaultdict

import qrcode
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string, get_template
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView
from weasyprint import HTML
from xhtml2pdf import pisa

from inhp.backends import PatientAuthBackend
from inhp.models import Patient, Vaccination, Maladie


# Create your views here.


class HomePageView(LoginRequiredMixin, TemplateView):
    login_url = '/accounts/login/'
    # form_class = LoginForm
    template_name = "pages/home.html"


class LandingView(TemplateView):

    template_name = "publiq/landing.html"


def patient_login_view(request):
    if request.method == 'POST':
        code_patient = request.POST.get('code_patient')
        telephone = request.POST.get('telephone')
        backend = PatientAuthBackend()
        user = backend.authenticate(request, code_patient=code_patient, telephone=telephone)
        if user:
            login(request, user, backend='inhp.backends.PatientAuthBackend')
            return redirect('patient_dashboard')  # Vue spéciale patient
        else:
            messages.error(request, 'Code patient ou téléphone incorrect.')
    return render(request, 'patient_space/patient_login.html')


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
