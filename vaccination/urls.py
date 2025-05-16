"""
URL configuration for vaccination project.

The `urlpatterns` list routes URLs to  For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django_prometheus import exports
from django_prometheus.views import ExportToDjangoView

from inhp.views import HomePageView, patient_login_view, patient_dashboard, mes_vaccins, generate_pdf_certificat, \
    verifier_certificat, LandingView, DashboardView, PatientListView, PatientCreateView, PatientDetailView, \
    PatientUpdateView, PatientDeleteView, MapiListView, MapiCreateView, MapiUpdateView, MapiDetailView, MapiDeleteView, \
    VaccineExtListView, VaccineExtCreateView, VaccineExtDeleteView, VaccineExtUpdateView, VaccineExtDetailView

urlpatterns = [
                  path('admin/', admin.site.urls),

                  path("metrics/", ExportToDjangoView.as_view()),

                  path('api-auth/', include('rest_framework.urls')),
                  path('accounts/', include('allauth.urls')),
                  path('', LandingView.as_view(), name='landing'),
                  path('home', HomePageView.as_view(), name='home'),
                  path('connexion/patient/', patient_login_view, name='patient_login'),
                  path('dashboard/patient/', patient_dashboard, name='patient_dashboard'),
                  path('mes-vaccins/', mes_vaccins, name='mes_vaccins'),
                  path('certificat/<int:maladie_id>', generate_pdf_certificat, name='certificat'),
                  path('certificat/verifier_certificat/<int:maladie_id>/<int:patient_id>', verifier_certificat,
                       name='verifier_certificat'),
                  # ----------------------Admin ----------------urls
                  path('dashboard', DashboardView.as_view(), name='dashboard'),

                  path('patients/', PatientListView.as_view(), name='patient-list'),
                  path('patients/create/', PatientCreateView.as_view(), name='patient-create'),
                  path('patients/<str:code_patient>/', PatientDetailView.as_view(), name='patient-detail'),
                  path('patients/<str:code_patient>/update/', PatientUpdateView.as_view(), name='patient-update'),
                  path('patients/<str:code_patient>/delete/', PatientDeleteView.as_view(), name='patient-delete'),
                  # path('patients/<str:code_patient>/mapis/', PatientMapiListView.as_view(), name='patient-mapis'),
                  # path('patients/<str:code_patient>/vaccine-exts/', PatientVaccineExtListView.as_view(),
                  #      name='patient-vaccine-exts'),

                  # Mapi URLs
                  path('mapis/', MapiListView.as_view(), name='mapi-list'),
                  path('mapis/create/', MapiCreateView.as_view(), name='mapi-create'),
                  path('mapis/<int:pk>/', MapiDetailView.as_view(), name='mapi-detail'),
                  path('mapis/<int:pk>/update/', MapiUpdateView.as_view(), name='mapi-update'),
                  path('mapis/<int:pk>/delete/', MapiDeleteView.as_view(), name='mapi-delete'),

                  # VaccineExt URLs
                  path('vaccine-exts/', VaccineExtListView.as_view(), name='vaccine-ext-list'),
                  path('vaccine-exts/create/', VaccineExtCreateView.as_view(), name='vaccine-ext-create'),
                  path('vaccine-exts/<int:pk>/', VaccineExtDetailView.as_view(), name='vaccine-ext-detail'),
                  path('vaccine-exts/<int:pk>/update/', VaccineExtUpdateView.as_view(),
                       name='vaccine-ext-update'),
                  path('vaccine-exts/<int:pk>/delete/', VaccineExtDeleteView.as_view(),
                       name='vaccine-ext-delete'),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
