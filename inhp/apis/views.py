from datetime import timedelta, date

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Q, Min, Max
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets, permissions, generics, filters, status
from rest_framework.decorators import permission_classes, api_view, action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView

from inhp.apis.serializers import UtilisateurSerializer, PatientSerializer, VaccinSerializer, MapiSerializer, \
    VaccineExtSerializer, VaccinationSerializer, FicheRetroSerializer, VaccinationListSerializer, \
    VaccinationDetailSerializer, VaccinationCreateSerializer, VaccinationUpdateSerializer
from inhp.backends import StaffOnlyMixin
from inhp.models import Utilisateur, Patient, CentreBasedPermission, Vaccin, Vaccination, Mapi, VaccineExt, \
    CentreVaccination, FicheRetro, LotVaccin, AccessLevel
from inhp.views import DashboardStatsMixin


class DashboardStatsAPIView(StaffOnlyMixin, DashboardStatsMixin, APIView):
    """
    API JSON pour recharger le dashboard côté front (Alpine/JS)
    en fonction :
    - de la période (30d / quarter / year)
    - de la maladie (disease_id)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        period = request.query_params.get("period", "30d")
        disease_id = request.query_params.get("disease_id", None)

        data = self._build_dashboard_data(
            user=request.user,
            period=period,
            disease_id=disease_id,
        )
        return Response(data)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            # "phone": user.phone,
            # "role": user.role,
        })


class UtilisateurViewSet(viewsets.ModelViewSet):
    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stats_and_centres(request):
    today = now().date()
    one_week_ago = today - timedelta(days=7)

    total = Patient.objects.count()
    new = Patient.objects.filter(created_at__date__gte=one_week_ago).count()
    active = Patient.objects.filter(is_active=True).count() if hasattr(Patient, 'actif') else 0
    inactive = total - active

    centres = CentreVaccination.objects.all()
    centres_data = [{"id": c.id, "name": c.name} for c in centres]

    return Response({
        "stats": {
            "total": total,
            "new": new,
            "active": active,
            "inactive": inactive,
        },
        "centres": centres_data,
    })


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    # permission_classes = [permissions.IsAuthenticated, CentreBasedPermission]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    filterset_fields = ['code_patient', 'telephone1', 'centre_actuel', 'created_at']
    search_fields = ['nom', 'prenoms']

    # search_fields = ['nom', 'prenoms', 'telephone1', 'code_patient']  # ← adapte selon ton modèle


class VaccinationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class VaccinationViewSet(viewsets.ModelViewSet):
    """
    API Vaccinations avec filtrage avancé, statistiques
    ET scope par access_level (centre / district / région / pôle / national).
    """
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    pagination_class = VaccinationPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    # DjangoFilterBackend remplacé par get_queryset custom
    filterset_fields = ['centre', 'vaccin', 'dose']
    search_fields = ['patient__nom', 'patient__prenoms', 'vaccin__nom', 'centre__name']
    ordering_fields = ['date_vaccination', 'date_rappel', 'created_at', 'dose']
    ordering = ['-date_vaccination']

    # ---------------------------------------------------
    # 1) Scope par access_level
    # ---------------------------------------------------
    def _apply_access_level_scope(self, qs):
        """
        Limite le queryset au périmètre de l'utilisateur connecté
        selon access_level : centre / district / région / pôle / national.
        """
        user = self.request.user

        # Si pas d'access_level (cas admin technique, scripts, etc.) -> on ne restreint pas.
        if not hasattr(user, "access_level"):
            return qs

        # CENTRE
        if user.access_level == AccessLevel.CENTRE and getattr(user, "centre_id", None):
            return qs.filter(centre=user.centre)

        # DISTRICT
        if user.access_level == AccessLevel.DISTRICT and getattr(user, "district_id", None):
            return qs.filter(centre__district=user.district)

        # REGION
        if user.access_level == AccessLevel.REGION and getattr(user, "region_id", None):
            return qs.filter(centre__district__region=user.region)

        # POLE
        if user.access_level == AccessLevel.POLE and getattr(user, "pole_id", None):
            return qs.filter(centre__district__region__poles=user.pole)

        # NATIONAL -> pas de restriction
        # (AccessLevel.NATIONAL)
        return qs

    # ---------------------------------------------------
    # 2) Queryset principal avec filtres GET
    # ---------------------------------------------------
    def get_queryset(self):
        qs = (
            Vaccination.objects.all().select_related('patient', 'centre', 'vaccin', 'lot', 'created_by')
        )

        # 🔒 Scope access_level
        qs = self._apply_access_level_scope(qs)

        params = self.request.query_params

        # 🔹 Filtre patient texte (code, nom, prénom, téléphone)
        patient_value = (params.get('patient') or '').strip()
        if patient_value:
            qs = qs.filter(
                Q(patient__code_patient__icontains=patient_value) |
                Q(patient__nom__icontains=patient_value) |
                Q(patient__prenoms__icontains=patient_value) |
                Q(patient__telephone1__icontains=patient_value)
            )

        # 🔹 Filtre centre, vaccin, dose
        centre_id = (params.get('centre') or '').strip()
        if centre_id:
            qs = qs.filter(centre_id=centre_id)

        vaccin_id = (params.get('vaccin') or '').strip()
        if vaccin_id:
            qs = qs.filter(vaccin_id=vaccin_id)

        dose = (params.get('dose') or '').strip()
        if dose:
            qs = qs.filter(dose=dose)

        # 🔹 Filtre dates (en nettoyant les espaces & \xa0)
        raw_debut = (params.get('date_debut') or '').replace('\xa0', ' ').strip()
        raw_fin = (params.get('date_fin') or '').replace('\xa0', ' ').strip()

        date_debut = parse_date(raw_debut) if raw_debut else None
        date_fin = parse_date(raw_fin) if raw_fin else None

        if date_debut or date_fin:
            if date_debut:
                qs = qs.filter(date_vaccination__gte=date_debut)
            if date_fin:
                qs = qs.filter(date_vaccination__lte=date_fin)
        else:
            # Si tu veux limiter par défaut à 90 jours, décommente :
            # default_start = timezone.now().date() - timedelta(days=90)
            # qs = qs.filter(date_vaccination__gte=default_start)
            pass

        return qs

    # ---------------------------------------------------
    # 3) Serializers
    # ---------------------------------------------------
    def get_serializer_class(self):
        if self.action == 'list':
            return VaccinationListSerializer
        elif self.action == 'retrieve':
            return VaccinationDetailSerializer
        elif self.action == 'create':
            return VaccinationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return VaccinationUpdateSerializer
        return VaccinationListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save()

    # ---------------------------------------------------
    # 4) Rappels (prochains / manqués) → scoping aussi
    # ---------------------------------------------------
    @action(detail=False, methods=['get'])
    def rappels_prochains(self, request):
        date_limit = timezone.now().date() + timedelta(days=30)

        qs = (
            Vaccination.objects
            .filter(
                date_rappel__isnull=False,
                date_rappel__gte=timezone.now().date(),
                date_rappel__lte=date_limit,
            )
            .select_related('patient', 'vaccin', 'centre')
        )

        qs = self._apply_access_level_scope(qs)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = VaccinationListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = VaccinationListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def rappels_manques(self, request):
        qs = (
            Vaccination.objects
            .filter(
                date_rappel__isnull=False,
                date_rappel__lt=timezone.now().date(),
            )
            .select_related('patient', 'vaccin', 'centre')
        )

        qs = self._apply_access_level_scope(qs)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = VaccinationListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = VaccinationListSerializer(qs, many=True)
        return Response(serializer.data)

    # ---------------------------------------------------
    # 5) Statistiques → TOUT passe par le qs scoppé
    # ---------------------------------------------------
    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        """
        Statistiques filtrées par access_level :
        - périodes (mois / semaine / 30j)
        - répartitions (vaccin / centre / dose)
        - KPIs (rappels, activité récente, couverture de patients, centres actifs, etc.)
        """
        base_qs = Vaccination.objects.all()
        base_qs = self._apply_access_level_scope(base_qs)

        today = date.today()
        six_months_ago = today - timedelta(days=180)

        # --- PÉRIODES ---------------------------------------------
        vaccinations_par_mois = (
            base_qs.filter(date_vaccination__gte=six_months_ago)
            .annotate(mois=TruncMonth('date_vaccination'))
            .values('mois')
            .annotate(total=Count('id'))
            .order_by('mois')
        )

        vaccinations_par_semaine = (
            base_qs.filter(date_vaccination__gte=today - timedelta(days=84))
            .annotate(semaine=TruncWeek('date_vaccination'))
            .values('semaine')
            .annotate(total=Count('id'))
            .order_by('semaine')
        )

        # Série journalière sur 30 jours (pour mini-barres ou analyse fine)
        vaccinations_30j_series = (
            base_qs.filter(date_vaccination__gte=today - timedelta(days=30))
            .values('date_vaccination')
            .annotate(total=Count('id'))
            .order_by('date_vaccination')
        )

        # Rappels planifiés sur les 30 prochains jours
        rappels_par_jour = (
            base_qs.filter(
                date_rappel__isnull=False,
                date_rappel__gte=today,
                date_rappel__lte=today + timedelta(days=30),
            )
            .values('date_rappel')
            .annotate(total=Count('id'))
            .order_by('date_rappel')
        )

        # --- RÉPARTITIONS -----------------------------------------
        total_global = base_qs.count() or 1

        vaccinations_par_vaccin_raw = (
            base_qs
            .values('vaccin__nom', 'vaccin__id')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        vaccinations_par_vaccin = [
            {
                **row,
                'pourcentage': (row['total'] * 100.0) / total_global
            }
            for row in vaccinations_par_vaccin_raw
        ]

        vaccinations_par_centre_raw = (
            base_qs
            .values('centre__name', 'centre__id')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        vaccinations_par_centre = [
            {
                **row,
                'pourcentage': (row['total'] * 100.0) / total_global
            }
            for row in vaccinations_par_centre_raw
        ]

        vaccinations_par_dose_raw = (
            base_qs
            .values('dose')
            .annotate(total=Count('id'))
            .order_by('dose')
        )
        vaccinations_par_dose = [
            {
                **row,
                'pourcentage': (row['total'] * 100.0) / total_global
            }
            for row in vaccinations_par_dose_raw
        ]

        # --- KPIs GLOBAUX ----------------------------------------
        rappels_prochains = base_qs.filter(
            date_rappel__isnull=False,
            date_rappel__gte=today,
            date_rappel__lte=today + timedelta(days=30),
        ).count()

        rappels_manques = base_qs.filter(
            date_rappel__isnull=False,
            date_rappel__lt=today,
        ).count()

        vaccinations_aujourdhui = base_qs.filter(
            date_vaccination=today
        ).count()

        debut_semaine = today - timedelta(days=today.weekday())
        vaccinations_semaine = base_qs.filter(
            date_vaccination__gte=debut_semaine
        ).count()

        debut_mois = today.replace(day=1)
        vaccinations_mois = base_qs.filter(
            date_vaccination__gte=debut_mois
        ).count()

        mois_precedent_debut = (debut_mois - timedelta(days=1)).replace(day=1)
        mois_precedent_fin = debut_mois - timedelta(days=1)

        vaccinations_mois_precedent = base_qs.filter(
            date_vaccination__gte=mois_precedent_debut,
            date_vaccination__lte=mois_precedent_fin
        ).count()

        evolution_mois = 0
        if vaccinations_mois_precedent > 0:
            evolution_mois = (
                                     (vaccinations_mois - vaccinations_mois_precedent)
                                     / vaccinations_mois_precedent
                             ) * 100

        total_rappels = rappels_prochains + rappels_manques
        taux_rappel = (rappels_prochains * 100.0 / total_rappels) if total_rappels > 0 else 0

        # Centres actifs (ayant au moins une vaccination dans le scope)
        centres_actifs = base_qs.values('centre_id').distinct().count()

        # Patients uniques vaccinés (dans le scope)
        patients_vaccines = base_qs.values('patient_id').distinct().count()

        # Activité récente
        vaccinations_7j = base_qs.filter(
            date_vaccination__gte=today - timedelta(days=7)
        ).count()
        vaccinations_30j = base_qs.filter(
            date_vaccination__gte=today - timedelta(days=30)
        ).count()

        # Plage d’historique
        agg_dates = base_qs.aggregate(
            premiere_vaccination=Min('date_vaccination'),
            derniere_vaccination=Max('date_vaccination'),
        )

        return Response({
            'periodes': {
                'vaccinations_par_mois': list(vaccinations_par_mois),
                'vaccinations_par_semaine': list(vaccinations_par_semaine),
                'vaccinations_30j_series': list(vaccinations_30j_series),
                'rappels_par_jour': list(rappels_par_jour),
            },
            'repartition': {
                'par_vaccin': vaccinations_par_vaccin,
                'par_centre': vaccinations_par_centre,
                'par_dose': list(vaccinations_par_dose_raw),
                'par_dose_detaille': vaccinations_par_dose,
            },
            'kpis': {
                'total_vaccinations': total_global,
                'vaccinations_aujourdhui': vaccinations_aujourdhui,
                'vaccinations_semaine': vaccinations_semaine,
                'vaccinations_mois': vaccinations_mois,
                'evolution_mois': round(evolution_mois, 1),
                'rappels_prochains': rappels_prochains,
                'rappels_manques': rappels_manques,
                'taux_rappel': round(taux_rappel, 1),
                'centres_actifs': centres_actifs,
                'patients_vaccines': patients_vaccines,
                'vaccinations_7j': vaccinations_7j,
                'vaccinations_30j': vaccinations_30j,
                'premiere_vaccination': agg_dates['premiere_vaccination'],
                'derniere_vaccination': agg_dates['derniere_vaccination'],
            }
        })


# class VaccinationViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet pour la gestion des vaccinations
#     """
#     queryset = Vaccination.objects.filter(deleted_at__isnull=True)
#     permission_classes = [IsAuthenticated, DjangoModelPermissions]
#     pagination_class = VaccinationPagination
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#
#     # ⚠️ on laisse le backend gérer centre/vaccin/dose,
#     # mais on gère le filtre patient nous-mêmes (texte libre)
#     filterset_fields = ['centre', 'vaccin', 'dose']
#
#     search_fields = ['patient__nom', 'patient__prenoms', 'vaccin__nom', 'centre__name']
#     ordering_fields = ['date_vaccination', 'date_rappel', 'created_at', 'dose']
#     ordering = ['-date_vaccination']
#
#     def get_queryset(self):
#         qs = Vaccination.objects.filter(deleted_at__isnull=True).select_related(
#             'patient', 'centre', 'vaccin', 'lot', 'created_by'
#         )
#
#         request = self.request
#         params = request.query_params
#
#         # 🔹 Filtre patient texte (code, nom, prénom, téléphone)
#         patient_value = params.get('patient')
#         if patient_value:
#             qs = qs.filter(
#                 Q(patient__code_patient__icontains=patient_value) |
#                 Q(patient__nom__icontains=patient_value) |
#                 Q(patient__prenoms__icontains=patient_value) |
#                 Q(patient__telephone1__icontains=patient_value)
#             )
#
#         # 🔹 Filtre dates
#         date_debut = params.get('date_debut')
#         date_fin = params.get('date_fin')
#
#         if not date_debut and not date_fin:
#             # si aucune date fournie => 90 derniers jours par défaut
#             default_start = timezone.now().date() - timedelta(days=90)
#             qs = qs.filter(date_vaccination__gte=default_start)
#         else:
#             if date_debut:
#                 qs = qs.filter(date_vaccination__gte=date_debut)
#             if date_fin:
#                 qs = qs.filter(date_vaccination__lte=date_fin)
#
#         return qs
#
#     def get_serializer_class(self):
#         if self.action == 'list':
#             return VaccinationListSerializer
#         elif self.action == 'retrieve':
#             return VaccinationDetailSerializer
#         elif self.action == 'create':
#             return VaccinationCreateSerializer
#         elif self.action in ['update', 'partial_update']:
#             return VaccinationUpdateSerializer
#         return VaccinationListSerializer
#
#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user)
#
#     def perform_destroy(self, instance):
#         instance.deleted_at = timezone.now()
#         instance.save()
#
#     @action(detail=False, methods=['get'])
#     def rappels_prochains(self, request):
#         date_limit = timezone.now().date() + timedelta(days=30)
#         vaccinations = Vaccination.objects.filter(
#             deleted_at__isnull=True,
#             date_rappel__isnull=False,
#             date_rappel__gte=timezone.now().date(),
#             date_rappel__lte=date_limit
#         ).order_by('date_rappel')
#
#         page = self.paginate_queryset(vaccinations)
#         if page is not None:
#             serializer = VaccinationListSerializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#
#         serializer = VaccinationListSerializer(vaccinations, many=True)
#         return Response(serializer.data)
#
#     @action(detail=False, methods=['get'])
#     def rappels_manques(self, request):
#         vaccinations = Vaccination.objects.filter(
#             deleted_at__isnull=True,
#             date_rappel__isnull=False,
#             date_rappel__lt=timezone.now().date()
#         ).order_by('date_rappel')
#
#         page = self.paginate_queryset(vaccinations)
#         if page is not None:
#             serializer = VaccinationListSerializer(page, many=True)
#             return self.get_paginated_response(serializer.data)
#
#         serializer = VaccinationListSerializer(vaccinations, many=True)
#         return Response(serializer.data)
#
#     @action(detail=False, methods=['get'])
#     def statistiques(self, request):
#         six_months_ago = timezone.now().date() - timedelta(days=180)
#
#         vaccinations_par_mois = Vaccination.objects.filter(
#             deleted_at__isnull=True,
#             date_vaccination__gte=six_months_ago
#         ).extra({
#             'mois': "EXTRACT(month FROM date_vaccination)",
#             'annee': "EXTRACT(year FROM date_vaccination)"
#         }).values('mois', 'annee').annotate(total=Count('id')).order_by('annee', 'mois')
#
#         vaccinations_par_vaccin = Vaccination.objects.filter(
#             deleted_at__isnull=True
#         ).values('vaccin__nom').annotate(total=Count('id')).order_by('-total')
#
#         vaccinations_par_centre = Vaccination.objects.filter(
#             deleted_at__isnull=True
#         ).values('centre__name').annotate(total=Count('id')).order_by('-total')
#
#         rappels_prochains = Vaccination.objects.filter(
#             deleted_at__isnull=True,
#             date_rappel__isnull=False,
#             date_rappel__gte=date.today()
#         ).count()
#
#         rappels_manques = Vaccination.objects.filter(
#             deleted_at__isnull=True,
#             date_rappel__isnull=False,
#             date_rappel__lt=date.today()
#         ).count()
#
#         return Response({
#             'vaccinations_par_mois': list(vaccinations_par_mois),
#             'vaccinations_par_vaccin': list(vaccinations_par_vaccin),
#             'vaccinations_par_centre': list(vaccinations_par_centre),
#             'rappels_prochains': rappels_prochains,
#             'rappels_manques': rappels_manques,
#             'total_vaccinations': Vaccination.objects.filter(deleted_at__isnull=True).count()
#         })


class VaccinationCustomAPIView(viewsets.ViewSet):
    """
    Vue API personnalisée pour les opérations spécifiques sur les vaccinations
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='patient/(?P<patient_id>[^/.]+)')
    def vaccinations_patient(self, request, patient_id=None):
        """
        Retourne toutes les vaccinations d'un patient spécifique
        """
        try:
            vaccinations = Vaccination.objects.filter(
                patient_id=patient_id,
                deleted_at__isnull=True
            ).order_by('-date_vaccination')

            serializer = VaccinationListSerializer(vaccinations, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], url_path='calculer-rappel')
    def calculer_date_rappel(self, request):
        """
        Calcule la date de rappel basée sur le vaccin et la date de vaccination
        """
        vaccin_id = request.data.get('vaccin_id')
        date_vaccination = request.data.get('date_vaccination')

        if not vaccin_id or not date_vaccination:
            return Response(
                {'error': 'vaccin_id et date_vaccination sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            vaccin = Vaccin.objects.get(id=vaccin_id)
            date_vaccination = timezone.datetime.strptime(date_vaccination, '%Y-%m-%d').date()

            if vaccin.besoin_rappel and vaccin.duree_immunite:
                date_rappel = date_vaccination + relativedelta(months=vaccin.duree_immunite)
                return Response({'date_rappel_calculee': date_rappel})
            else:
                return Response({'date_rappel_calculee': None})

        except Vaccin.DoesNotExist:
            return Response(
                {'error': 'Vaccin non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LotsParVaccinAPIView(APIView):
    """
    API pour récupérer les lots disponibles pour un vaccin spécifique
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, vaccin_id):
        try:
            lots = LotVaccin.objects.filter(
                vaccin_id=vaccin_id,
                stock__gt=0,
                date_expiration__gt=timezone.now().date()
            ).select_related('vaccin')

            data = [{
                'id': lot.id,
                'numero_lot': lot.numero_lot,
                'stock': lot.stock,
                'date_expiration': lot.date_expiration
            } for lot in lots]

            return Response({'lots': data})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class VaccinViewSet(viewsets.ModelViewSet):
    queryset = Vaccin.objects.all()
    serializer_class = VaccinSerializer
    permission_classes = [permissions.IsAuthenticated]


class PatientListCreateView(generics.ListCreateAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'code_patient': ['exact', 'icontains'],
        'nom': ['exact', 'icontains'],
        'prenoms': ['exact', 'icontains'],
        'date_naissance': ['exact', 'gte', 'lte'],
        'sexe': ['exact'],
        'telephone1': ['exact', 'icontains'],
        'statut': ['exact'],
        'centre': ['exact'],
        'created_at': ['gte', 'lte'],
    }

    search_fields = ['code_patient', 'nom', 'prenoms', 'telephone1', 'telephone2', 'num_piece']
    ordering_fields = ['nom', 'prenoms', 'date_naissance', 'created_at']
    ordering = ['nom']


class PatientRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'code_patient'

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save()


class MapiListCreateView(generics.ListCreateAPIView):
    queryset = Mapi.objects.all()
    serializer_class = MapiSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'patient': ['exact'],
        'centre': ['exact'],
        'vaccination': ['exact'],
        'utilisateur': ['exact'],
        'date': ['exact', 'gte', 'lte'],
        'created_at': ['gte', 'lte'],
    }

    search_fields = ['symptome', 'commentaire']
    ordering_fields = ['date', 'created_at']
    ordering = ['-date']


class MapiRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Mapi.objects.all()
    serializer_class = MapiSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save()


class VaccineExtListCreateView(generics.ListCreateAPIView):
    queryset = VaccineExt.objects.all()
    serializer_class = VaccineExtSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = {
        'patient': ['exact'],
        'vaccin': ['exact'],
        'utilisateur': ['exact'],
        'date': ['exact', 'gte', 'lte'],
        'numero_dose': ['exact', 'gte', 'lte'],
        'created_at': ['gte', 'lte'],
    }

    search_fields = ['pays', 'ville', 'lot', 'code_patient']
    ordering_fields = ['date', 'numero_dose', 'created_at']
    ordering = ['-date']


class VaccineExtRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = VaccineExt.objects.all()
    serializer_class = VaccineExtSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save()


class PatientVaccinationsListView(generics.ListAPIView):
    """Liste des vaccinations d'un patient"""
    serializer_class = VaccinationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        code_patient = self.kwargs['code_patient']
        return Vaccination.objects.filter(patient__code_patient=code_patient)


class PatientMapisListView(generics.ListAPIView):
    """Liste des MAPI d'un patient"""
    serializer_class = MapiSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        code_patient = self.kwargs['code_patient']
        return Mapi.objects.filter(patient__code_patient=code_patient)


class PatientVaccineExtsListView(generics.ListAPIView):
    """Liste des vaccins externes d'un patient"""
    serializer_class = VaccineExtSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        code_patient = self.kwargs['code_patient']
        return VaccineExt.objects.filter(patient__code_patient=code_patient)


class FicheRetroViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 10))
        offset = (page - 1) * per_page

        queryset = FicheRetro.objects.all().order_by('-created_at')
        total = queryset.count()
        results = queryset[offset:offset + per_page]
        serializer = FicheRetroSerializer(results, many=True)

        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'per_page': per_page
        })


@api_view(['GET'])
def fiche_retro_stats(request):
    total = FicheRetro.objects.count()
    positives = FicheRetro.objects.filter(positif=1).count()
    new_last_7_days = FicheRetro.objects.filter(created_at__gte=now() - timedelta(days=7)).count()

    return Response({
        'total': total,
        'positives': positives,
        'new_last_7_days': new_last_7_days,
    })
