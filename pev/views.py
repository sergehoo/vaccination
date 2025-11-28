from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.forms import DateInput
from django.views.decorators.http import require_GET
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg, F, Max
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
import json
import csv
from datetime import datetime, timedelta

from inhp.forms import PEVCampaignTeamForm, PatientQuickForm, VaccinationForm, VaccinationCampainForm
from .models import PEVCampaign, PEVCampaignTeam, PEVCampaignStatus, PEVCampaignType, PEVCampaignFrequency, \
    PEVCampaignTeamType
from inhp.models import ServiceVaccination, CentreVaccination, DistrictSanitaire, HealthRegion, PolesRegionaux, Vaccin, \
    Utilisateur, Patient, Vaccination, LotVaccin


class PEVCampaignListView(LoginRequiredMixin, ListView):
    """Liste des campagnes PEV avec filtres et recherche"""
    model = PEVCampaign
    template_name = 'administration/pev/campaign_list.html'
    context_object_name = 'campagnes'
    paginate_by = 20

    def get_queryset(self):
        queryset = PEVCampaign.objects.select_related(
            'service', 'created_by', 'responsable_campagne'
        ).prefetch_related(
            'vaccins', 'poles', 'regions', 'districts', 'centres'
        ).filter(actif=True)

        # Filtres
        statut = self.request.GET.get('statut')
        if statut:
            queryset = queryset.filter(statut=statut)

        type_campagne = self.request.GET.get('type_campagne')
        if type_campagne:
            queryset = queryset.filter(type_campagne=type_campagne)

        annee = self.request.GET.get('annee')
        if annee:
            queryset = queryset.filter(date_debut__year=annee)

        service = self.request.GET.get('service')
        if service:
            queryset = queryset.filter(service_id=service)

        # Recherche
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(nom__icontains=search) |
                Q(nom_court__icontains=search) |
                Q(description__icontains=search)
            )

        # Tri
        sort = self.request.GET.get('sort', '-date_creation')
        if sort in ['code', 'nom', 'date_debut', 'date_fin', 'statut', 'type_campagne']:
            queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques pour les filtres
        context['statuts'] = PEVCampaignStatus.choices
        context['types_campagne'] = PEVCampaignType.choices
        context['services'] = ServiceVaccination.objects.filter(actif=True)

        # Années disponibles
        annees = PEVCampaign.objects.dates('date_debut', 'year')
        context['annees'] = [date.year for date in annees]

        # Statistiques globales
        context['stats_globales'] = {
            'total': PEVCampaign.objects.filter(actif=True).count(),
            'en_cours': PEVCampaign.objects.filter(
                statut=PEVCampaignStatus.EN_COURS,
                actif=True
            ).count(),
            'planifiees': PEVCampaign.objects.filter(
                statut=PEVCampaignStatus.PLANIFIEE,
                actif=True
            ).count(),
            'cloturees': PEVCampaign.objects.filter(
                statut=PEVCampaignStatus.CLOTUREE,
                actif=True
            ).count(),
        }

        return context


# class PEVCampaignDetailView(LoginRequiredMixin, DetailView):
#     """Détail d'une campagne PEV avec stats enrichies."""
#     model = PEVCampaign
#     template_name = 'administration/pev/campaign_detail.html'
#     context_object_name = 'campagne'
#
#     def get_utilisateur(self):
#         """Retourne un objet Utilisateur à partir de request.user si possible."""
#         u = self.request.user
#
#         # Si c’est déjà un Utilisateur (cas normal)
#         if isinstance(u, Utilisateur):
#             return u
#
#         # Si tu as un OneToOne du type user.utilisateur
#         if hasattr(u, "utilisateur"):
#             return u.utilisateur
#
#         # Fallback : on essaie de retrouver par email
#         if u.email:
#             try:
#                 return Utilisateur.objects.get(email=u.email)
#             except (Utilisateur.DoesNotExist, Utilisateur.MultipleObjectsReturned):
#                 pass
#
#         return None
#
#     def get_queryset(self):
#         # On optimise au maximum les requêtes
#         return (
#             PEVCampaign.objects
#             .select_related('service', 'created_by', 'responsable_campagne')
#             .prefetch_related(
#                 'vaccins',
#                 'poles',
#                 'regions',
#                 'districts',
#                 'centres',
#                 # on précharge les équipes et leurs relations
#                 'equipes__membres',
#                 'equipes__pole',
#                 'equipes__region',
#                 'equipes__district',
#                 'equipes__centre',
#             )
#         )
#
#     def _compute_time_progression(self, campagne):
#         today = timezone.now().date()
#         if not (campagne.date_debut and campagne.date_fin):
#             return {
#                 'jours_ecoules': 0,
#                 'jours_restants': 0,
#                 'pourcentage': 0,
#                 'etat_temps': 'non_defini',
#             }
#
#         duree_totale = (campagne.date_fin - campagne.date_debut).days or 1
#         jours_ecoules = (today - campagne.date_debut).days
#         jours_restants = (campagne.date_fin - today).days
#
#         pourcentage = min(100, max(0, (jours_ecoules / duree_totale) * 100))
#
#         # état temporel
#         if today < campagne.date_debut:
#             etat_temps = 'pas_commencee'
#         elif campagne.date_debut <= today <= campagne.date_fin:
#             etat_temps = 'en_cours'
#         else:
#             # après la date de fin
#             etat_temps = 'terminee'
#             # si statut != cloturée, on peut considérer "en_retard"
#             if campagne.statut not in ['cloturee', 'suspendue']:
#                 etat_temps = 'en_retard'
#
#         return {
#             'jours_ecoules': max(0, jours_ecoules),
#             'jours_restants': max(0, jours_restants),
#             'pourcentage': round(pourcentage, 1),
#             'etat_temps': etat_temps,
#         }
#
#     def _compute_team_stats(self, campagne):
#         equipes = campagne.equipes.all()
#
#         total_equipes = equipes.count()
#         equipes_actives = equipes.filter(actif=True).count()
#
#         agg = equipes.aggregate(
#             total_enfants_vaccines=Sum('enfants_vaccines'),
#             total_doses_administrees=Sum('doses_administrees'),
#             moyenne_doses_equipe=Avg('doses_administrees'),
#             moyenne_enfants_equipe=Avg('enfants_vaccines'),
#         )
#
#         total_enfants = agg['total_enfants_vaccines'] or 0
#         total_doses = agg['total_doses_administrees'] or 0
#
#         # Couverture réelle calculée à partir des équipes si possible
#         couverture_reelle_calc = 0
#         if campagne.population_cible:
#             couverture_reelle_calc = (total_enfants / campagne.population_cible) * 100
#
#         return {
#             'equipes': equipes,
#             'total_equipes': total_equipes,
#             'equipes_actives': equipes_actives,
#             'personnel_total': sum(
#                 equipe.membres.count() + (1 if equipe.responsable else 0)
#                 for equipe in equipes
#             ),
#             'moyenne_doses_equipe': agg['moyenne_doses_equipe'] or 0,
#             'moyenne_enfants_equipe': agg['moyenne_enfants_equipe'] or 0,
#             'total_enfants_vaccines': total_enfants,
#             'total_doses_administrees': total_doses,
#             'couverture_reelle_calc': couverture_reelle_calc,
#             'taux_activation_equipes': (
#                 (equipes_actives / total_equipes) * 100 if total_equipes else 0
#             ),
#         }
#
#     def _compute_budget_stats(self, campagne):
#         budget_alloue = campagne.budget_alloue or 0
#         budget_depense = campagne.budget_depense or 0
#
#         budget_utilise_calc = 0
#         if budget_alloue > 0:
#             budget_utilise_calc = min(100, (budget_depense / budget_alloue) * 100)
#
#         return {
#             'budget_alloue': budget_alloue,
#             'budget_depense': budget_depense,
#             'budget_utilise_calc': budget_utilise_calc,
#             'budget_restant': max(0, budget_alloue - budget_depense),
#         }
#
#     def _compute_zone_stats(self, campagne):
#         return {
#             'nb_poles': campagne.poles.count(),
#             'nb_regions': campagne.regions.count(),
#             'nb_districts': campagne.districts.count(),
#             'nb_centres': campagne.centres.count(),
#             'nb_centres_geo': campagne.centres.exclude(
#                 Q(latitude__isnull=True) | Q(longitude__isnull=True)
#             ).count(),
#         }
#
#     def _compute_rapport_stats(self, campagne):
#         meta = campagne.meta or {}
#         rapports_jour = meta.get('rapports_jour', []) or []
#
#         # On s’assure que c’est bien une liste triée par date si possible
#         try:
#             rapports_jour = sorted(
#                 rapports_jour,
#                 key=lambda r: r.get('date') or '',
#             )
#         except Exception:
#             pass
#
#         derniers_rapports = rapports_jour[-7:]
#
#         total_enfants = sum(r.get('enfants_vaccines', 0) for r in rapports_jour)
#         total_doses = sum(r.get('doses_administrees', 0) for r in rapports_jour)
#         total_incidents = sum(r.get('incidents', 0) for r in rapports_jour)
#
#         return {
#             'rapports_jour': rapports_jour,
#             'derniers_rapports': derniers_rapports,
#             'total_enfants_rapports': total_enfants,
#             'total_doses_rapports': total_doses,
#             'total_incidents_rapports': total_incidents,
#         }
#
#     def _compute_actions_flags(self, campagne):
#         util = self.get_utilisateur
#         # can_change = util.has_perm('inhp.change_pevcampaign')
#
#         return {
#             # 'can_start': can_change and campagne.statut == 'planifiee',
#             # 'can_suspend': can_change and campagne.statut == 'en_cours',
#             # 'can_resume': can_change and campagne.statut == 'suspendue',
#             # 'can_close': can_change and campagne.statut == 'en_cours',
#         }
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         campagne = self.object
#
#         campagne: PEVCampaign = self.object
#
#         # ---------- FILTRES ----------
#         request = self.request
#         q = request.GET.get("q", "").strip()
#         centre_id = request.GET.get("centre") or None
#         vaccin_id = request.GET.get("vaccin") or None
#         equipe_id = request.GET.get("equipe") or None
#         vaccinateur_id = request.GET.get("vaccinateur") or None
#         date_debut = request.GET.get("date_debut") or None
#         date_fin = request.GET.get("date_fin") or None
#
#         vacc_qs = (
#             Vaccination.objects
#             .filter(
#                 campagne_pev=campagne,
#                 deleted_at__isnull=True,
#             )
#             .select_related(
#                 "patient", "centre", "vaccin",
#                 "equipe", "vaccinateur",
#             )
#             .order_by("-date_vaccination", "-created_at")
#         )
#
#         if q:
#             vacc_qs = vacc_qs.filter(
#                 Q(patient__nom__icontains=q) |
#                 Q(patient__prenoms__icontains=q) |
#                 Q(patient__code_patient__icontains=q) |
#                 Q(patient__telephone1__icontains=q)
#             )
#
#         if centre_id:
#             vacc_qs = vacc_qs.filter(centre_id=centre_id)
#
#         if vaccin_id:
#             vacc_qs = vacc_qs.filter(vaccin_id=vaccin_id)
#
#         if equipe_id:
#             vacc_qs = vacc_qs.filter(equipe_id=equipe_id)
#
#         if vaccinateur_id:
#             vacc_qs = vacc_qs.filter(vaccinateur_id=vaccinateur_id)
#
#         if date_debut:
#             vacc_qs = vacc_qs.filter(date_vaccination__gte=date_debut)
#
#         if date_fin:
#             vacc_qs = vacc_qs.filter(date_vaccination__lte=date_fin)
#
#         # ---------- PAGINATION ----------
#         paginator = Paginator(vacc_qs, 25)  # 25 vaccinations par page
#         page_number = request.GET.get("page")
#         page_obj = paginator.get_page(page_number)
#
#         # ---------- LISTES POUR LES SELECTS ----------
#         context["vaccinations_page"] = page_obj
#         context["vaccinations_total"] = vacc_qs.count()
#
#         # pour les filtres : on se base sur les données de la campagne
#         context["filter_centres"] = campagne.centres_impliques()
#         context["filter_vaccins"] = campagne.vaccins.all()
#
#         from pev.models import PEVCampaignTeam
#         from inhp.models import Utilisateur
#
#         context["filter_equipes"] = PEVCampaignTeam.objects.filter(
#             campagne=campagne
#         ).order_by("code")
#
#         context["filter_vaccinateurs"] = (
#             Utilisateur.objects.filter(
#                 vaccinations_administrees__campagne_pev=campagne
#             )
#             .distinct()
#             .order_by("first_name", "last_name")
#         )
#         context["vaccinations_filters"] = {
#             "q": q,
#             "centre": centre_id,
#             "vaccin": vaccin_id,
#             "equipe": equipe_id,
#             "vaccinateur": vaccinateur_id,
#             "date_debut": date_debut,
#             "date_fin": date_fin,
#         }
#         # Équipes & stats
#         team_stats = self._compute_team_stats(campagne)
#         context['equipes'] = team_stats['equipes']
#         context['stats_detaillees'] = {
#             'total_equipes': team_stats['total_equipes'],
#             'equipes_actives': team_stats['equipes_actives'],
#             'personnel_total': team_stats['personnel_total'],
#             'moyenne_doses_equipe': team_stats['moyenne_doses_equipe'],
#             'moyenne_enfants_equipe': team_stats['moyenne_enfants_equipe'],
#             'total_enfants_vaccines': team_stats['total_enfants_vaccines'],
#             'total_doses_administrees': team_stats['total_doses_administrees'],
#             'taux_activation_equipes': team_stats['taux_activation_equipes'],
#             'couverture_reelle_calc': team_stats['couverture_reelle_calc'],
#         }
#
#         # Progression temporelle
#         context['progression_temps'] = self._compute_time_progression(campagne)
#
#         # Budget
#         context['budget_stats'] = self._compute_budget_stats(campagne)
#
#         # Zones
#         context['zones_stats'] = self._compute_zone_stats(campagne)
#
#         # Rapports
#         rapport_stats = self._compute_rapport_stats(campagne)
#         context['derniers_rapports'] = rapport_stats['derniers_rapports']
#         context['rapport_stats'] = rapport_stats
#
#         # Flags d’actions pour simplifier le template
#         context['actions_flags'] = self._compute_actions_flags(campagne)
#
#         return context

class PEVCampaignDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une campagne PEV avec stats enrichies."""
    model = PEVCampaign
    template_name = 'administration/pev/campaign_detail.html'
    context_object_name = 'campagne'

    # ---------- HELPERS ----------

    def get_utilisateur(self) -> Utilisateur | None:
        """
        Retourne un objet Utilisateur à partir de request.user si possible.
        Gère le cas où tu utilises le User Django natif + un profil Utilisateur.
        """
        u = self.request.user

        # Déjà un Utilisateur (cas où AUTH_USER_MODEL = Utilisateur)
        if isinstance(u, Utilisateur):
            return u

        # OneToOne : user.utilisateur
        if hasattr(u, "utilisateur"):
            return u.utilisateur

        # Fallback par email
        if u.email:
            try:
                return Utilisateur.objects.get(email=u.email)
            except (Utilisateur.DoesNotExist, Utilisateur.MultipleObjectsReturned):
                return None
        return None

    def get_queryset(self):
        # Optimisation des requêtes
        return (
            PEVCampaign.objects
            .select_related('service', 'created_by', 'responsable_campagne')
            .prefetch_related(
                'vaccins',
                'poles',
                'regions',
                'districts',
                'centres',
                'equipes__membres',
                'equipes__pole',
                'equipes__region',
                'equipes__district',
                'equipes__centre',
            )
        )

    # ---------- BLOCS DE CALCULS ----------

    def _compute_time_progression(self, campagne: PEVCampaign) -> dict:
        today = timezone.now().date()
        if not (campagne.date_debut and campagne.date_fin):
            return {
                'jours_ecoules': 0,
                'jours_restants': 0,
                'pourcentage': 0,
                'etat_temps': 'non_defini',
            }

        duree_totale = (campagne.date_fin - campagne.date_debut).days or 1
        jours_ecoules = (today - campagne.date_debut).days
        jours_restants = (campagne.date_fin - today).days
        pourcentage = min(100, max(0, (jours_ecoules / duree_totale) * 100))

        if today < campagne.date_debut:
            etat_temps = 'pas_commencee'
        elif campagne.date_debut <= today <= campagne.date_fin:
            etat_temps = 'en_cours'
        else:
            etat_temps = 'terminee'
            if campagne.statut not in ['cloturee', 'suspendue']:
                etat_temps = 'en_retard'

        return {
            'jours_ecoules': max(0, jours_ecoules),
            'jours_restants': max(0, jours_restants),
            'pourcentage': round(pourcentage, 1),
            'etat_temps': etat_temps,
        }

    def _compute_team_stats(self, campagne: PEVCampaign) -> dict:
        equipes = campagne.equipes.all()

        total_equipes = equipes.count()
        equipes_actives = equipes.filter(actif=True).count()

        agg = equipes.aggregate(
            total_enfants_vaccines=Sum('enfants_vaccines'),
            total_doses_administrees=Sum('doses_administrees'),
            moyenne_doses_equipe=Avg('doses_administrees'),
            moyenne_enfants_equipe=Avg('enfants_vaccines'),
        )

        total_enfants = agg['total_enfants_vaccines'] or 0
        total_doses = agg['total_doses_administrees'] or 0

        couverture_reelle_calc = 0
        if campagne.population_cible:
            couverture_reelle_calc = (total_enfants / campagne.population_cible) * 100

        return {
            'equipes': equipes,
            'total_equipes': total_equipes,
            'equipes_actives': equipes_actives,
            'personnel_total': sum(
                equipe.membres.count() + (1 if equipe.responsable else 0)
                for equipe in equipes
            ),
            'moyenne_doses_equipe': agg['moyenne_doses_equipe'] or 0,
            'moyenne_enfants_equipe': agg['moyenne_enfants_equipe'] or 0,
            'total_enfants_vaccines': total_enfants,
            'total_doses_administrees': total_doses,
            'couverture_reelle_calc': couverture_reelle_calc,
            'taux_activation_equipes': (
                (equipes_actives / total_equipes) * 100 if total_equipes else 0
            ),
        }

    def _compute_budget_stats(self, campagne: PEVCampaign) -> dict:
        budget_alloue = campagne.budget_alloue or 0
        budget_depense = campagne.budget_depense or 0

        budget_utilise_calc = 0
        if budget_alloue > 0:
            budget_utilise_calc = min(100, (budget_depense / budget_alloue) * 100)

        return {
            'budget_alloue': budget_alloue,
            'budget_depense': budget_depense,
            'budget_utilise_calc': budget_utilise_calc,
            'budget_restant': max(0, budget_alloue - budget_depense),
        }

    def _compute_zone_stats(self, campagne: PEVCampaign) -> dict:
        return {
            'nb_poles': campagne.poles.count(),
            'nb_regions': campagne.regions.count(),
            'nb_districts': campagne.districts.count(),
            'nb_centres': campagne.centres.count(),
            'nb_centres_geo': campagne.centres.exclude(
                Q(latitude__isnull=True) | Q(longitude__isnull=True)
            ).count(),
        }

    def _compute_rapport_stats(self, campagne: PEVCampaign) -> dict:
        meta = campagne.meta or {}
        rapports_jour = meta.get('rapports_jour', []) or []

        try:
            rapports_jour = sorted(
                rapports_jour,
                key=lambda r: r.get('date') or '',
            )
        except Exception:
            pass

        derniers_rapports = rapports_jour[-7:]

        total_enfants = sum(r.get('enfants_vaccines', 0) for r in rapports_jour)
        total_doses = sum(r.get('doses_administrees', 0) for r in rapports_jour)
        total_incidents = sum(r.get('incidents', 0) for r in rapports_jour)

        return {
            'rapports_jour': rapports_jour,
            'derniers_rapports': derniers_rapports,
            'total_enfants_rapports': total_enfants,
            'total_doses_rapports': total_doses,
            'total_incidents_rapports': total_incidents,
        }

    def _compute_actions_flags(self, campagne: PEVCampaign) -> dict:
        util = self.get_utilisateur()
        # Exemple si tu veux réactiver la gestion de droits :
        # can_change = util and util.has_perm('pev.change_pevcampaign')
        return {
            # 'can_start': can_change and campagne.statut == PEVCampaignStatus.PLANIFIEE,
            # ...
        }

    # ---------- CONTEXT ----------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campagne: PEVCampaign = self.object
        request = self.request

        # ----- FILTRES LISTE DES VACCINATIONS -----
        q = request.GET.get("q", "").strip()
        centre_id = request.GET.get("centre") or None
        vaccin_id = request.GET.get("vaccin") or None
        equipe_id = request.GET.get("equipe") or None
        vaccinateur_id = request.GET.get("vaccinateur") or None
        date_debut = request.GET.get("date_debut") or None
        date_fin = request.GET.get("date_fin") or None

        vacc_qs = (
            Vaccination.objects
            .filter(
                campagne_pev=campagne,
                deleted_at__isnull=True,
            )
            .select_related(
                "patient",
                "centre",
                "vaccin",
                "equipe",
                "vaccinateur",
            )
            .order_by("-date_vaccination", "-created_at")
        )

        if q:
            vacc_qs = vacc_qs.filter(
                Q(patient__nom__icontains=q) |
                Q(patient__prenoms__icontains=q) |
                Q(patient__code_patient__icontains=q) |
                Q(patient__telephone1__icontains=q)
            )

        if centre_id:
            vacc_qs = vacc_qs.filter(centre_id=centre_id)
        if vaccin_id:
            vacc_qs = vacc_qs.filter(vaccin_id=vaccin_id)
        if equipe_id:
            vacc_qs = vacc_qs.filter(equipe_id=equipe_id)
        if vaccinateur_id:
            vacc_qs = vacc_qs.filter(vaccinateur_id=vaccinateur_id)
        if date_debut:
            vacc_qs = vacc_qs.filter(date_vaccination__gte=date_debut)
        if date_fin:
            vacc_qs = vacc_qs.filter(date_vaccination__lte=date_fin)

        paginator = Paginator(vacc_qs, 25)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["vaccinations_page"] = page_obj
        context["vaccinations_total"] = vacc_qs.count()

        # Filtres pour les <select>
        context["filter_centres"] = campagne.centres_impliques()
        context["filter_vaccins"] = campagne.vaccins.all()
        context["filter_equipes"] = PEVCampaignTeam.objects.filter(
            campagne=campagne
        ).order_by("code")
        context["filter_vaccinateurs"] = (
            Utilisateur.objects.filter(
                vaccinations_administrees__campagne_pev=campagne
            )
            .distinct()
            .order_by("first_name", "last_name")
        )
        context["vaccinations_filters"] = {
            "q": q,
            "centre": centre_id,
            "vaccin": vaccin_id,
            "equipe": equipe_id,
            "vaccinateur": vaccinateur_id,
            "date_debut": date_debut,
            "date_fin": date_fin,
        }

        # ----- STATS CAMPAGNE -----
        team_stats = self._compute_team_stats(campagne)
        context['equipes'] = team_stats['equipes']
        context['stats_detaillees'] = {
            'total_equipes': team_stats['total_equipes'],
            'equipes_actives': team_stats['equipes_actives'],
            'personnel_total': team_stats['personnel_total'],
            'moyenne_doses_equipe': team_stats['moyenne_doses_equipe'],
            'moyenne_enfants_equipe': team_stats['moyenne_enfants_equipe'],
            'total_enfants_vaccines_equipes': team_stats['total_enfants_vaccines'],
            'total_doses_administrees_equipes': team_stats['total_doses_administrees'],
            'taux_activation_equipes': team_stats['taux_activation_equipes'],
            'couverture_reelle_calc_equipes': team_stats['couverture_reelle_calc'],
        }

        # Indicateurs calculés à partir des vaccinations
        context["indicateurs_campagne"] = {
            "nombre_enfants_vaccines": campagne.nombre_enfants_vaccines_calc,
            "doses_administrees": campagne.doses_administrees_calc,
            "incidents_signales": campagne.incidents_signales_calc,
            "taux_couverture_reel": campagne.taux_couverture_reel,
            "taux_effets_secondaires": campagne.taux_effets_secondaires,
        }

        context['progression_temps'] = self._compute_time_progression(campagne)
        context['budget_stats'] = self._compute_budget_stats(campagne)
        context['zones_stats'] = self._compute_zone_stats(campagne)

        rapport_stats = self._compute_rapport_stats(campagne)
        context['derniers_rapports'] = rapport_stats['derniers_rapports']
        context['rapport_stats'] = rapport_stats

        context['actions_flags'] = self._compute_actions_flags(campagne)

        return context
class PEVCampaignTeamCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PEVCampaignTeam
    form_class = PEVCampaignTeamForm
    template_name = "administration/pev/team_form.html"
    permission_required = "inhp.add_pevcampaignteam"

    def dispatch(self, request, *args, **kwargs):
        self.campagne = get_object_or_404(PEVCampaign, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["campagne"] = self.campagne
        return context

    def form_valid(self, form):
        # Lier automatiquement la campagne à l'équipe
        form.instance.campagne = self.campagne

        # Vérifier unicité du code dans la campagne
        if PEVCampaignTeam.objects.filter(
            campagne=self.campagne,
            code=form.cleaned_data["code"],
        ).exists():
            form.add_error(
                "code",
                f"Une équipe avec le code '{form.cleaned_data['code']}' existe déjà pour cette campagne.",
            )
            return self.form_invalid(form)

        # Sauvegarde classique de l'équipe
        response = super().form_valid(form)
        team: PEVCampaignTeam = self.object

        # ------------------------------------------------------------------
        # Construire la liste des utilisateurs à notifier (responsable,
        # membres + utilisateurs liés à la zone de l'équipe)
        # ------------------------------------------------------------------
        user_ids = set()

        # 1) Responsable
        if team.responsable_id:
            user_ids.add(team.responsable_id)

        # 2) Membres M2M
        membres_ids = team.membres.values_list("id", flat=True)
        user_ids.update(membres_ids)

        # 3) Utilisateurs par zone (centre / district / région / pôle)
        zone_q = Q(is_active=True)

        has_zone = False
        if team.centre_id:
            zone_q &= Q(centre=team.centre)
            has_zone = True
        elif team.district_id:
            zone_q &= Q(district=team.district)
            has_zone = True
        elif team.region_id:
            zone_q &= Q(region=team.region)
            has_zone = True
        elif team.pole_id:
            zone_q &= Q(pole=team.pole)
            has_zone = True

        if has_zone:
            zone_users = Utilisateur.objects.filter(zone_q).exclude(
                phone__isnull=True
            ).exclude(
                phone__exact=""
            ).values_list("id", flat=True)
            user_ids.update(zone_users)

        # 4) Lancer la tâche Celery si on a au moins une personne
        if user_ids:
            from pev.tasks import notify_team_assignment
            notify_team_assignment.delay(team.id, list(user_ids))

        messages.success(
            self.request,
            f"Équipe {team.code} créée avec succès. "
            f"{len(user_ids)} membre(s) seront notifiés par SMS.",
        )

        return response

    def get_success_url(self):
        return reverse("pev:campaign_detail", kwargs={"pk": self.campagne.pk})

class PEVCampaignCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PEVCampaign
    template_name = 'administration/pev/campaign_form.html'
    permission_required = 'inhp.add_pevcampaign'
    fields = [
        'service', 'code', 'nom', 'nom_court', 'type_campagne', 'frequence',
        'description', 'objectifs', 'date_debut', 'date_fin',
        'age_min_mois', 'age_max_mois', 'population_cible', 'couverture_cible',
        'budget_alloue', 'vaccins', 'poles', 'regions', 'districts', 'centres',
        'plan_communication', 'partenaires_impliques', 'besoin_logistique',
        'responsable_campagne', 'remuneration_mode', 'montant_par_vaccination',
    ]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Service du user (lecture only dans le template)
        service = getattr(self.request.user, "service", None)

        # On enlève service & code du form si tu veux les gérer en backend
        form.fields.pop('service', None)
        form.fields.pop('code', None)

        # Widgets Date → indispensable pour préremplir
        form.fields['date_debut'].widget = DateInput(attrs={
            'type': 'date'
        }, format='%Y-%m-%d')

        form.fields['date_fin'].widget = DateInput(attrs={
            'type': 'date'
        }, format='%Y-%m-%d')

        # Responsable campagne : utilisateurs de ton modèle Utilisateur
        # from account.models import Utilisateur
        form.fields['responsable_campagne'].queryset = Utilisateur.objects.filter(
            is_active=True,
            groups__name__in=['Responsable PEV', 'Superviseur']
        ).order_by('first_name', 'last_name')

        return form

    def get_context_data(self, **kwargs):
        from inhp.models import PolesRegionaux, HealthRegion, DistrictSanitaire, CentreVaccination

        context = super().get_context_data(**kwargs)

        service = getattr(self.request.user, "service", None)
        context['service_auto'] = service

        # Utilise la méthode de classe
        context['code_auto'] = PEVCampaign.generate_next_code(
            service=service,
            type_campagne=context["form"].instance.type_campagne or None
        )

        context['geo_data'] = {
            "poles": list(PolesRegionaux.objects.values('id', 'name')),
            "regions": list(HealthRegion.objects.values('id', 'name', 'poles_id')),
            "districts": list(DistrictSanitaire.objects.values('id', 'nom', 'region_id')),
            "centres": list(CentreVaccination.objects.values('id', 'name', 'district_id')),
        }
        return context

    def form_valid(self, form):
        user = self.request.user
        form.instance.created_by = user
        form.instance.service = getattr(user, "service", None)

        if not form.instance.code:
            form.instance.code = PEVCampaign.generate_next_code(
                service=form.instance.service,
                type_campagne=form.instance.type_campagne,
            )

        form.instance.statut = PEVCampaignStatus.BROUILLON

        response = super().form_valid(form)
        campagne = self.object

        # ⚠️ équipe par défaut très simple
        try:
            campagne.create_team(
                code=f"{campagne.code}-EQ01",
                nom=f"Équipe principale {campagne.nom}",
                type_equipe=PEVCampaignTeamType.FIXE,
                poles=campagne.poles.all(),
                regions=campagne.regions.all(),
                districts=campagne.districts.all(),
                centres=campagne.centres.all(),
                responsable=campagne.responsable_campagne,
                membres=None,
            )
        except ValidationError as e:
            # On log l’erreur, mais on ne bloque pas la création de campagne
            # logger.warning(f"Erreur création équipe auto pour {campagne.code}: {e}")
            pass

        messages.success(self.request, f"Campagne {campagne.code} créée avec succès.")
        return response

    def form_invalid(self, form):
        # Debug rapide
        print("FORM INVALID:", form.errors)
        messages.error(self.request, "Le formulaire comporte des erreurs, veuillez vérifier les champs.")
        return super().form_invalid(form)
    def get_success_url(self):
        return reverse_lazy('pev:campaign_detail', kwargs={'pk': self.object.pk})


class PEVCampaignUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Modification d'une campagne PEV"""
    model = PEVCampaign
    template_name = 'pev/campaign_form.html'
    permission_required = 'inhp.change_pevcampaign'
    fields = [
        'service', 'code', 'nom', 'nom_court', 'type_campagne', 'frequence',
        'description', 'objectifs', 'date_debut', 'date_fin',
        'date_debut_reelle', 'date_fin_reelle', 'statut',
        'age_min_mois', 'age_max_mois', 'population_cible', 'couverture_cible',
        'budget_alloue', 'budget_depense', 'vaccins', 'poles', 'regions', 'districts', 'centres',
        'nombre_enfants_vaccines', 'doses_administrees', 'incidents_signales',
        'equipes_mobiles', 'personnel_implique',
        'plan_communication', 'partenaires_impliques', 'besoin_logistique',
        'statut_approvisionnement', 'responsable_campagne', 'meta'
    ]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Restrictions selon le statut
        if self.object.statut in [PEVCampaignStatus.CLOTUREE, PEVCampaignStatus.ARCHIVEE]:
            for field in form.fields:
                if field not in ['meta', 'budget_depense', 'date_fin_reelle']:
                    form.fields[field].disabled = True
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Campagne {self.object.code} modifiée avec succès.")
        return response

    def get_success_url(self):
        return reverse_lazy('pev_campaign_detail', kwargs={'pk': self.object.pk})


class PEVCampaignDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Suppression (désactivation) d'une campagne PEV"""
    model = PEVCampaign
    template_name = 'pev/campaign_confirm_delete.html'
    permission_required = 'inhp.delete_pevcampaign'
    success_url = reverse_lazy('pev_campaign_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.actif = False
        self.object.save()
        messages.success(request, f"Campagne {self.object.code} a été désactivée.")
        return redirect(self.success_url)


class PEVCampaignActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Vue pour les actions sur les campagnes (démarrer, clore, suspendre, etc.)"""
    permission_required = 'inhp.change_pevcampaign'

    def post(self, request, pk, action):
        campagne = get_object_or_404(PEVCampaign, pk=pk, actif=True)

        success = False
        message = ""

        if action == 'demarrer':
            if campagne.demarrer_campagne():
                success = True
                message = "Campagne démarrée avec succès."

        elif action == 'clore':
            if campagne.clore_campagne():
                success = True
                message = "Campagne clôturée avec succès."

        elif action == 'suspendre':
            motif = request.POST.get('motif', '')
            if campagne.suspendre_campagne(motif):
                success = True
                message = "Campagne suspendue avec succès."

        elif action == 'reprendre':
            if campagne.reprendre_campagne():
                success = True
                message = "Campagne reprise avec succès."

        elif action == 'archiver':
            campagne.statut = PEVCampaignStatus.ARCHIVEE
            campagne.save()
            success = True
            message = "Campagne archivée avec succès."

        if success:
            messages.success(request, message)
        else:
            messages.error(request, "Action impossible dans l'état actuel de la campagne.")

        return redirect('pev_campaign_detail', pk=campagne.pk)


class PEVCampaignDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord des campagnes PEV"""
    template_name = 'pev/campaign_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Campagnes en cours
        campagnes_en_cours = PEVCampaign.objects.filter(
            statut=PEVCampaignStatus.EN_COURS,
            actif=True
        ).select_related('service')

        # Campagnes à venir (30 prochains jours)
        date_limite = timezone.now().date() + timedelta(days=30)
        campagnes_a_venir = PEVCampaign.objects.filter(
            date_debut__lte=date_limite,
            statut=PEVCampaignStatus.PLANIFIEE,
            actif=True
        )

        # Statistiques par type de campagne
        stats_par_type = PEVCampaign.objects.filter(
            actif=True,
            date_debut__year=timezone.now().year
        ).values('type_campagne').annotate(
            total=Count('id'),
            enfants_vaccines=Sum('nombre_enfants_vaccines'),
            doses_administrees=Sum('doses_administrees')
        )

        # Alertes
        alertes = []
        for campagne in campagnes_en_cours:
            if campagne.jours_restants < 7:
                alertes.append(f"La campagne {campagne.nom} se termine dans {campagne.jours_restants} jours")

            if campagne.budget_utilise > 90:
                alertes.append(f"Budget de {campagne.nom} utilisé à {campagne.budget_utilise:.1f}%")

        context.update({
            'campagnes_en_cours': campagnes_en_cours,
            'campagnes_a_venir': campagnes_a_venir,
            'stats_par_type': stats_par_type,
            'alertes': alertes,
            'stats_globales': PEVCampaign.statistiques_globales(),
        })

        return context


class PEVCampaignRapportView(LoginRequiredMixin, DetailView):
    """Génération de rapports pour une campagne"""
    model = PEVCampaign
    template_name = 'pev/campaign_rapport.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campagne = self.object

        # Performance par équipe
        performance_equipes = campagne.equipes.annotate(
            efficacite=Sum('doses_administrees') / Sum('enfants_vaccines') * 100
        ).values('code', 'nom', 'enfants_vaccines', 'doses_administrees', 'efficacite')

        # Statistiques temporelles
        rapports_jour = campagne.meta.get('rapports_jour', [])

        context.update({
            'performance_equipes': performance_equipes,
            'rapports_jour': rapports_jour,
            'centres_impliques_count': campagne.centres_impliques().count(),
        })

        return context


class PEVCampaignExportView(LoginRequiredMixin, View):
    """Export des données de campagne"""

    def get(self, request, pk, format_type):
        campagne = get_object_or_404(PEVCampaign, pk=pk, actif=True)

        if format_type == 'csv':
            return self.export_csv(campagne)
        elif format_type == 'json':
            return self.export_json(campagne)
        else:
            messages.error(request, "Format d'export non supporté")
            return redirect('pev_campaign_detail', pk=pk)

    def export_csv(self, campagne):
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = f'attachment; filename="campagne_{campagne.code}_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Campagne PEV - Rapport détaillé'])
        writer.writerow(['Code', campagne.code])
        writer.writerow(['Nom', campagne.nom])
        writer.writerow(['Statut', campagne.get_statut_display()])
        writer.writerow(['Période', f"{campagne.date_debut} à {campagne.date_fin}"])
        writer.writerow([])

        # Statistiques principales
        writer.writerow(['STATISTIQUES PRINCIPALES'])
        writer.writerow(['Enfants vaccinés', campagne.nombre_enfants_vaccines])
        writer.writerow(['Doses administrées', campagne.doses_administrees])
        writer.writerow(
            ['Couverture réelle', f"{campagne.taux_couverture_reel}%" if campagne.taux_couverture_reel else 'N/A'])
        writer.writerow(['Incidents signalés', campagne.incidents_signales])
        writer.writerow([])

        # Équipes
        writer.writerow(['ÉQUIPES'])
        writer.writerow(['Code', 'Nom', 'Enfants vaccinés', 'Doses administrées', 'Incidents'])
        for equipe in campagne.equipes.all():
            writer.writerow([
                equipe.code, equipe.nom, equipe.enfants_vaccines,
                equipe.doses_administrees, equipe.incidents_signales
            ])

        return response

    def export_json(self, campagne):
        data = {
            'campagne': {
                'code': campagne.code,
                'nom': campagne.nom,
                'statut': campagne.statut,
                'type': campagne.type_campagne,
                'periode': {
                    'debut': campagne.date_debut.isoformat(),
                    'fin': campagne.date_fin.isoformat(),
                    'debut_reel': campagne.date_debut_reelle.isoformat() if campagne.date_debut_reelle else None,
                    'fin_reel': campagne.date_fin_reelle.isoformat() if campagne.date_fin_reelle else None,
                },
                'cible': {
                    'age_min_mois': campagne.age_min_mois,
                    'age_max_mois': campagne.age_max_mois,
                    'population_cible': campagne.population_cible,
                    'couverture_cible': float(campagne.couverture_cible) if campagne.couverture_cible else None,
                },
                'statistiques': {
                    'enfants_vaccines': campagne.nombre_enfants_vaccines,
                    'doses_administrees': campagne.doses_administrees,
                    'couverture_reelle': float(
                        campagne.taux_couverture_reel) if campagne.taux_couverture_reel else None,
                    'incidents': campagne.incidents_signales,
                    'taux_effets_secondaires': float(
                        campagne.taux_effets_secondaires) if campagne.taux_effets_secondaires else None,
                },
                'budget': {
                    'alloue': float(campagne.budget_alloue) if campagne.budget_alloue else None,
                    'depense': float(campagne.budget_depense) if campagne.budget_depense else None,
                    'utilise': float(campagne.budget_utilise) if campagne.budget_utilise else None,
                }
            },
            'equipes': list(campagne.equipes.values(
                'code', 'nom', 'type_equipe', 'enfants_vaccines',
                'doses_administrees', 'incidents_signales'
            )),
            'vaccins': list(campagne.vaccins.values('code', 'nom')),
            'metadata': {
                'export_le': timezone.now().isoformat(),
                'generateur': 'Système INHP PEV'
            }
        }

        response = JsonResponse(data, json_dumps_params={'indent': 2})
        response[
            'Content-Disposition'] = f'attachment; filename="campagne_{campagne.code}_{timezone.now().strftime("%Y%m%d")}.json"'
        return response


class PEVCampaignRapportJournalierView(LoginRequiredMixin, View):
    """Ajout d'un rapport journalier"""

    def post(self, request, pk):
        campagne = get_object_or_404(PEVCampaign, pk=pk, actif=True)

        try:
            data = json.loads(request.body)
            date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            enfants_vaccines = int(data['enfants_vaccines'])
            doses = int(data['doses_administrees'])
            incidents = int(data.get('incidents', 0))

            campagne.ajouter_rapport_jour(date, enfants_vaccines, doses, incidents)

            return JsonResponse({
                'success': True,
                'message': 'Rapport journalier ajouté avec succès',
                'stats_actualisees': {
                    'enfants_vaccines': campagne.nombre_enfants_vaccines,
                    'doses_administrees': campagne.doses_administrees,
                    'incidents': campagne.incidents_signales,
                    'couverture_reelle': float(
                        campagne.taux_couverture_reel) if campagne.taux_couverture_reel else None,
                }
            })

        except (KeyError, ValueError, json.JSONDecodeError) as e:
            return JsonResponse({
                'success': False,
                'message': 'Données invalides'
            }, status=400)


class PEVCampaignStatsAPIView(LoginRequiredMixin, View):
    """API pour les statistiques des campagnes"""

    def get(self, request):
        periode = request.GET.get('periode', 'annee_en_cours')  # annee_en_cours, 6_mois, 12_mois

        # Définition de la période
        today = timezone.now().date()
        if periode == '6_mois':
            date_debut = today - timedelta(days=180)
        elif periode == '12_mois':
            date_debut = today - timedelta(days=365)
        else:  # année en cours
            date_debut = today.replace(month=1, day=1)

        stats = PEVCampaign.objects.filter(
            actif=True,
            date_debut__gte=date_debut
        ).aggregate(
            total_campagnes=Count('id'),
            campagnes_terminees=Count('id', filter=Q(statut=PEVCampaignStatus.CLOTUREE)),
            campagnes_en_cours=Count('id', filter=Q(statut=PEVCampaignStatus.EN_COURS)),
            total_enfants_vaccines=Sum('nombre_enfants_vaccines'),
            total_doses=Sum('doses_administrees'),
            budget_total=Sum('budget_alloue'),
            budget_utilise=Sum('budget_depense')
        )

        # Statistiques par type
        stats_par_type = list(PEVCampaign.objects.filter(
            actif=True,
            date_debut__gte=date_debut
        ).values('type_campagne').annotate(
            count=Count('id'),
            enfants=Sum('nombre_enfants_vaccines'),
            doses=Sum('doses_administrees')
        ))

        return JsonResponse({
            'periode': {
                'debut': date_debut.isoformat(),
                'fin': today.isoformat()
            },
            'statistiques': stats,
            'par_type': stats_par_type
        })

class AgentPerformanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "administration/pev/agent_performance_dashboard.html"

    def _base_queryset(self):
        user = self.request.user

        qs = Vaccination.objects.select_related(
            "vaccinateur",
            "campagne_pev",
            "centre",
        ).filter(
            vaccinateur__service__code="PEV"   # 🔥 Filtre global ici
        )

        # 🔒 restriction centre par défaut (hors niveau national / superuser)
        access_level = getattr(user, "access_level", None)
        if not user.is_superuser and access_level not in ("national",):
            centre = getattr(user, "centre", None)
            if centre:
                qs = qs.filter(centre=centre)

        return qs

    def _apply_filters(self, qs):
        request = self.request
        campagne_id = request.GET.get("campagne")
        date_debut = request.GET.get("date_debut")
        date_fin = request.GET.get("date_fin")

        if campagne_id:
            qs = qs.filter(campagne_pev_id=campagne_id)

        if date_debut:
            qs = qs.filter(date_vaccination__gte=date_debut)
        if date_fin:
            qs = qs.filter(date_vaccination__lte=date_fin)

        return qs, {
            "campagne_id": campagne_id,
            "date_debut": date_debut,
            "date_fin": date_fin,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        qs = self._base_queryset()
        qs, filters = self._apply_filters(qs)

        # 🧮 agrégats par agent
        per_agent = (
            qs.values(
                "vaccinateur_id",
                "vaccinateur__first_name",
                "vaccinateur__last_name",
                "vaccinateur__email",
                "centre__name",
                # pour les nouvelles colonnes
                "equipe__code",
                "equipe__nom",
                "centre__district__nom",  # zone (district)
            )
            .annotate(
                nb_vaccinations=Count("id"),
                nb_enfants=Count("patient", distinct=True),
                # montant total = somme du montant par vaccination de chaque campagne
                montant_par_vaccination=Max("campagne_pev__montant_par_vaccination"),
                montant_total=Sum(F("campagne_pev__montant_par_vaccination")),
            )
            .order_by("-nb_vaccinations")
        )

        # stats globales
        global_stats = qs.aggregate(
            total_vaccinations=Count("id"),
            total_enfants=Count("patient", distinct=True),
            total_montant=Sum(F("campagne_pev__montant_par_vaccination")),
        )

        # bloc “moi”
        my_stats = None
        if qs.exists():
            my_row = next(
                (
                    row for row in per_agent
                    if row["vaccinateur_id"] == getattr(user, "id", None)
                ),
                None,
            )
            my_stats = my_row

        # campagnes pour filtre
        campagnes_qs = PEVCampaign.objects.all().order_by("-date_debut")

        ctx.update(
            {
                "filters": filters,
                "per_agent": per_agent,
                "global_stats": global_stats,
                "my_stats": my_stats,
                "campagnes": campagnes_qs,
            }
        )
        return ctx
# class VaccinationPosteCampagneView(LoginRequiredMixin, FormView):
#     """
#     Écran unique :
#     - recherche / création rapide patient
#     - formulaire vaccination lié à une campagne
#     """
#     template_name = "administration/pev/poste_campagne.html"
#     form_class = VaccinationForm
#
#     def dispatch(self, request, *args, **kwargs):
#         self.campagne = get_object_or_404(PEVCampaign, pk=kwargs.get("campagne_pk"))
#         return super().dispatch(request, *args, **kwargs)
#
#     def get_form_kwargs(self):
#         kwargs = super().get_form_kwargs()
#         # kwargs["request"] = self.request
#         # kwargs["campagne"] = self.campagne  # ✅ pour filtrer équipes / campagne
#
#         # Pré-remplir campagne si connue
#         initial = kwargs.get("initial", {})
#         initial.setdefault("campagne_pev", self.campagne)
#
#         # Si patient sélectionné (GET ou POST hidden field)
#         patient_id = self.request.POST.get("patient_id") or self.request.GET.get("patient")
#         if patient_id:
#             try:
#                 initial.setdefault("patient", Patient.objects.get(pk=patient_id))
#             except Patient.DoesNotExist:
#                 pass
#
#         kwargs["initial"] = initial
#         return kwargs
#
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         ctx["campagne"] = self.campagne
#
#         # Campagne en session pour les prochains actes
#         self.request.session["campagne_pev_courante"] = self.campagne.pk
#
#         # Formulaire de création rapide patient
#         user = self.request.user
#         service = getattr(user, "service", None)
#         centre = getattr(user, "centre", None)
#
#         ctx["patient_quick_form"] = PatientQuickForm(
#             service=service,
#             centre=centre,
#             created_by=user
#         )
#         return ctx
#
#     def form_valid(self, form):
#         vaccination = form.save(commit=False)
#         vaccination.created_by = self.request.user
#
#         # S'assurer que la campagne est bien celle du poste
#         if not vaccination.campagne_pev:
#             vaccination.campagne_pev = self.campagne
#
#         # centre / service default
#         if not vaccination.centre and hasattr(self.request.user, "centre"):
#             vaccination.centre = self.request.user.centre
#         if not vaccination.service and hasattr(self.request.user, "service"):
#             vaccination.service = self.request.user.service
#
#         # vaccinateur
#         if not vaccination.vaccinateur:
#             vaccination.vaccinateur = self.request.user
#
#         # date rappel
#         if not vaccination.date_rappel:
#             vaccination.date_rappel = vaccination.calculer_date_rappel()
#
#         vaccination.save()
#         return redirect("vaccination:poste_campagne", campagne_pk=self.campagne.pk)

@login_required
@require_GET
def api_lots_by_vaccin(request):
    vaccin_id = request.GET.get("vaccin")
    if not vaccin_id:
        return JsonResponse({"results": []})

    lots = (
        LotVaccin.objects
        .filter(vaccin_id=vaccin_id)
        .order_by("date_expiration", "numero_lot")
    )

    data = []
    for lot in lots:
        # numéro du lot
        numero = lot.numero_lot

        # texte expiration
        if lot.date_expiration:
            exp_str = lot.date_expiration.strftime("%d/%m/%Y")
            exp_part = f" (exp. {exp_str})"
        else:
            exp_part = ""

        # éventuellement quantité
        qte = lot.quantite_disponible if lot.quantite_disponible is not None else 0
        label = f"{numero}{exp_part} · {qte} dispo."

        data.append({
            "id": lot.id,
            "label": label,
        })

    return JsonResponse({"results": data})
class VaccinationPosteCampagneView(LoginRequiredMixin, FormView):
    template_name = "administration/pev/poste_campagne.html"
    form_class = VaccinationCampainForm

    def dispatch(self, request, *args, **kwargs):
        self.campagne = get_object_or_404(PEVCampaign, pk=kwargs.get("campagne_pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # On passe la requête (pour filtrer les champs dans le form si besoin)
        kwargs["request"] = self.request
        kwargs["campagne"] = self.campagne
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["campagne"] = self.campagne

        # Campagne courante en session
        self.request.session["campagne_pev_courante"] = self.campagne.pk

        util = self.get_utilisateur()
        service = getattr(util, "service", None) if util else None
        centre = getattr(util, "centre", None) if util else None

        ctx["patient_quick_form"] = PatientQuickForm(
            service=service,
            centre=centre,
            created_by=util,  # ✅ pas auth.User
        )
        return ctx
    def get_utilisateur(self):
        """Retourne un objet Utilisateur à partir de request.user si possible."""
        u = self.request.user

        # Si c’est déjà un Utilisateur (cas normal)
        if isinstance(u, Utilisateur):
            return u

        # Si tu as un OneToOne du type user.utilisateur
        if hasattr(u, "utilisateur"):
            return u.utilisateur

        # Fallback : on essaie de retrouver par email
        if u.email:
            try:
                return Utilisateur.objects.get(email=u.email)
            except (Utilisateur.DoesNotExist, Utilisateur.MultipleObjectsReturned):
                pass

        return None

    def form_valid(self, form):
        util = self.get_utilisateur()  # peut être None

        # 1) Patient
        patient_id = self.request.POST.get("patient_id")
        if not patient_id:
            form.add_error(None, "Veuillez d’abord sélectionner un patient.")
            return self.form_invalid(form)

        try:
            patient = Patient.objects.get(pk=patient_id)
        except Patient.DoesNotExist:
            form.add_error(None, "Patient sélectionné introuvable.")
            return self.form_invalid(form)

        vaccination = form.save(commit=False)
        vaccination.patient = patient

        # 2) Campagne forcée
        if not getattr(vaccination, "campagne_pev_id", None):
            vaccination.campagne_pev = self.campagne

        # 3) Centre obligatoire : on cherche partout
        centre = None
        if util and getattr(util, "centre_id", None):
            centre = util.centre
        elif getattr(self.request.user, "centre_id", None):
            centre = self.request.user.centre

        if not centre:
            form.add_error(
                None,
                "Impossible de déterminer votre centre de vaccination. "
                "Veuillez contacter l’administrateur pour rattacher votre compte à un centre."
            )
            return self.form_invalid(form)

        vaccination.centre = centre  # ✅ Jamais NULL

        # 4) Service (si dispo, sinon facultatif)
        if util and getattr(util, "service_id", None) and not getattr(vaccination, "service_id", None):
            vaccination.service = util.service
        elif getattr(self.request.user, "service_id", None) and not getattr(vaccination, "service_id", None):
            vaccination.service = self.request.user.service

        # 5) Vaccinateur / created_by → Utilisateur si possible
        if util:
            if not getattr(vaccination, "vaccinateur_id", None):
                vaccination.vaccinateur = util
            if not getattr(vaccination, "created_by_id", None):
                vaccination.created_by = util

        # 6) Date de rappel auto
        if not vaccination.date_rappel:
            vaccination.date_rappel = vaccination.calculer_date_rappel()

        vaccination.save()

        messages.success(self.request, "Vaccination enregistrée avec succès.")
        return redirect("pev:poste_campagne", campagne_pk=self.campagne.pk)

    def form_invalid(self, form):
        # Debug rapide
        print("FORM INVALID:", form.errors)
        messages.error(self.request, "Le formulaire comporte des erreurs, veuillez vérifier les champs.")
        return super().form_invalid(form)
class PatientQuickSearchView(LoginRequiredMixin, View):
    """
    API simple pour chercher un patient :
    - par code_patient
    - par nom + date de naissance
    - par téléphone
    """
    def get(self, request, *args, **kwargs):
        q = request.GET.get("q", "").strip()
        date_naissance = request.GET.get("date_naissance", "").strip()

        patients = Patient.objects.all()

        if q:
            patients = patients.filter(
                Q(code_patient__icontains=q) |
                Q(nom__icontains=q) |
                Q(prenoms__icontains=q) |
                Q(telephone1__icontains=q) |
                Q(telephone2__icontains=q)
            )

        if date_naissance:
            patients = patients.filter(date_naissance=date_naissance)

        patients = patients.order_by("nom", "prenoms")[:20]

        data = [
            {
                "id": p.id,
                "code_patient": p.code_patient,
                "nom_complet": p.get_full_name(),
                "date_naissance": p.date_naissance.isoformat(),
                "sexe": p.sexe,
                "telephone": p.telephone1,
            }
            for p in patients
        ]
        return JsonResponse({"results": data})
class PatientQuickCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user
        service = getattr(user, "service", None)
        centre = getattr(user, "centre", None)

        form = PatientQuickForm(
            data=request.POST,
            service=service,
            centre=centre,
            created_by=user
        )
        if form.is_valid():
            patient = form.save()
            return JsonResponse({
                "ok": True,
                "patient": {
                    "id": patient.id,
                    "code_patient": patient.code_patient,
                    "nom_complet": patient.get_full_name(),
                    "date_naissance": patient.date_naissance.isoformat(),
                    "sexe": patient.sexe,
                    "telephone": patient.telephone1,
                }
            })
        return JsonResponse({
            "ok": False,
            "errors": form.errors,
        }, status=400)