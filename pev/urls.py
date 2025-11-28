from django.conf import settings
from django.urls import path
from . import views
from django.conf.urls.static import static

from .views import PEVCampaignTeamCreateView, VaccinationPosteCampagneView, PatientQuickSearchView, \
    PatientQuickCreateView, api_lots_by_vaccin, AgentPerformanceDashboardView

app_name = 'pev'

urlpatterns = [
                  path('campagnes/', views.PEVCampaignListView.as_view(), name='campaign_list'),
                  path('campagnes/nouvelle/', views.PEVCampaignCreateView.as_view(), name='campaign_create'),
                  path('campagnes/<int:pk>/', views.PEVCampaignDetailView.as_view(), name='campaign_detail'),
                  path(
                      "campaign/<int:pk>/teams/new/",
                      PEVCampaignTeamCreateView.as_view(),
                      name="campaign_team_create",
                  ),
                  path('campagnes/<int:pk>/modifier/', views.PEVCampaignUpdateView.as_view(), name='campaign_update'),
                  path('campagnes/<int:pk>/supprimer/', views.PEVCampaignDeleteView.as_view(), name='campaign_delete'),
                  path('campagnes/<int:pk>/action/<str:action>/', views.PEVCampaignActionView.as_view(),
                       name='campaign_action'),
                  path('campagnes/<int:pk>/rapport/', views.PEVCampaignRapportView.as_view(), name='campaign_rapport'),
                  path('campagnes/<int:pk>/export/<str:format_type>/', views.PEVCampaignExportView.as_view(),
                       name='campaign_export'),
                  path('campagnes/<int:pk>/rapport-journalier/', views.PEVCampaignRapportJournalierView.as_view(),
                       name='campaign_rapport_journalier'),

                  path("lots-by-vaccin/", api_lots_by_vaccin, name="api_lots_by_vaccin"),
                  path("poste/campagne/<int:campagne_pk>/", VaccinationPosteCampagneView.as_view(),  name="poste_campagne"),
                  path("patients/search/",  PatientQuickSearchView.as_view(),  name="patient_search"),
                  path("patients/quick-create/",  PatientQuickCreateView.as_view(),  name="patient_quick_create"),

                  path("agents/performance/", AgentPerformanceDashboardView.as_view(),name="pev_agent_performance",),

                  path('tableau-de-bord/', views.PEVCampaignDashboardView.as_view(), name='dashboard'),
                  path('api/stats/', views.PEVCampaignStatsAPIView.as_view(), name='api_stats'),
              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
