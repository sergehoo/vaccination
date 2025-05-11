from django.urls import path, include
from rest_framework.routers import DefaultRouter

from inhp.apis.views import VaccinViewSet
from inhp.views import UtilisateurViewSet, PatientViewSet

router = DefaultRouter()
router.register(r'users', UtilisateurViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'vaccins', VaccinViewSet)


urlpatterns = [
    path('api/', include(router.urls)),
]