from django.urls import path, include
from rest_framework.routers import DefaultRouter

from inhp.apis.views import VaccinViewSet, UtilisateurViewSet, PatientViewSet, PatientListCreateView, \
    PatientRetrieveUpdateDestroyView, PatientVaccinationsListView, PatientMapisListView, PatientVaccineExtsListView, \
    MapiListCreateView, MapiRetrieveUpdateDestroyView, VaccineExtListCreateView, VaccineExtRetrieveUpdateDestroyView

# from inhp.views import UtilisateurViewSet, PatientViewSet

router = DefaultRouter()
router.register(r'users', UtilisateurViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'vaccins', VaccinViewSet)


urlpatterns = [
    path('api/', include(router.urls)),
    path('patients/', PatientListCreateView.as_view(), name='patient-list'),
    path('patients/<str:code_patient>/', PatientRetrieveUpdateDestroyView.as_view(), name='patient-detail'),
    path('patients/<str:code_patient>/vaccinations/', PatientVaccinationsListView.as_view(),
         name='patient-vaccinations'),
    path('patients/<str:code_patient>/mapis/', PatientMapisListView.as_view(), name='patient-mapis'),
    path('patients/<str:code_patient>/vaccine-exts/', PatientVaccineExtsListView.as_view(),
         name='patient-vaccine-exts'),

    # Mapi URLs
    path('mapis/', MapiListCreateView.as_view(), name='mapi-list'),
    path('mapis/<int:pk>/', MapiRetrieveUpdateDestroyView.as_view(), name='mapi-detail'),

    # VaccineExt URLs
    path('vaccine-exts/', VaccineExtListCreateView.as_view(), name='vaccine-ext-list'),
    path('vaccine-exts/<int:pk>/', VaccineExtRetrieveUpdateDestroyView.as_view(), name='vaccine-ext-detail'),
]