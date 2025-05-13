"""
URL configuration for vaccination project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
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

from inhp.views import HomePageView, patient_login_view, patient_dashboard, mes_vaccins, generate_pdf_certificat, \
    verifier_certificat, LandingView, DashboardView

urlpatterns = [
                  path('admin/', admin.site.urls),
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
                  #----------------------Admin ----------------urls
                  path('dashboard', DashboardView.as_view(), name='dashboard'),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
