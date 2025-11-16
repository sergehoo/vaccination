from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from inhp.apis.views import VaccinViewSet, UtilisateurViewSet, PatientViewSet, PatientListCreateView, \
    PatientRetrieveUpdateDestroyView, PatientVaccinationsListView, PatientMapisListView, PatientVaccineExtsListView, \
    MapiListCreateView, MapiRetrieveUpdateDestroyView, VaccineExtListCreateView, VaccineExtRetrieveUpdateDestroyView, \
    MeAPIView, stats_and_centres, FicheRetroViewSet, fiche_retro_stats, VaccinationViewSet, VaccinationCustomAPIView, \
    LotsParVaccinAPIView

# from inhp.views import UtilisateurViewSet, PatientViewSet

router = DefaultRouter()
router.register(r'users', UtilisateurViewSet)
router.register(r'patients', PatientViewSet)
router.register(r'vaccins', VaccinViewSet)
router.register(r'retrosaisie', FicheRetroViewSet, basename='retrosaisie')
router.register(r'vaccinations', VaccinationViewSet, basename='vaccination')
router.register(r'vaccinations-custom', VaccinationCustomAPIView, basename='vaccination-custom')

urlpatterns = [
    path('', include(router.urls)),
    path("api/me/", MeAPIView.as_view(), name="me"),
    path("patients/stats-and-centres/", stats_and_centres, name="stats-and-centres"),
    path('retrosaisie/stats', fiche_retro_stats),

    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path('patients/apis/create', PatientListCreateView.as_view(), name='patient-api-create'),
    path('patients/<str:code_patient>/', PatientRetrieveUpdateDestroyView.as_view(), name='patient-detail'),
    path('patients/<str:code_patient>/vaccinations/', PatientVaccinationsListView.as_view(),
         name='patient-vaccinations'),
    path('patients/<str:code_patient>/mapis/', PatientMapisListView.as_view(), name='patient-mapis'),
    path('patients/<str:code_patient>/vaccine-exts/', PatientVaccineExtsListView.as_view(),
         name='patient-vaccine-exts'),

    path('api/lots-par-vaccin/<int:vaccin_id>/',
         LotsParVaccinAPIView.as_view(),
         name='lots-par-vaccin'),

    # Mapi URLs
    path('mapis/', MapiListCreateView.as_view(), name='mapi-list'),
    path('mapis/<int:pk>/', MapiRetrieveUpdateDestroyView.as_view(), name='mapi-detail'),

    # VaccineExt URLs
    path('vaccine-exts/', VaccineExtListCreateView.as_view(), name='vaccine-ext-list'),
    path('vaccine-exts/<int:pk>/', VaccineExtRetrieveUpdateDestroyView.as_view(), name='vaccine-ext-detail'),
]
