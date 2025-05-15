from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, generics, filters

from inhp.apis.serializers import UtilisateurSerializer, PatientSerializer, VaccinSerializer, MapiSerializer, \
    VaccineExtSerializer, VaccinationSerializer
from inhp.models import Utilisateur, Patient, CentreBasedPermission, Vaccin, Vaccination, Mapi, VaccineExt


class UtilisateurViewSet(viewsets.ModelViewSet):
    queryset = Utilisateur.objects.all()
    serializer_class = UtilisateurSerializer
    permission_classes = [permissions.IsAuthenticated]


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated, CentreBasedPermission]

class VaccinViewSet(viewsets.ModelViewSet):
    queryset = Vaccin.objects.all()
    serializer_class = VaccinSerializer
    permission_classes = [permissions.IsAuthenticated]



class PatientListCreateView(generics.ListCreateAPIView):
    queryset = Patient.objects.filter(deleted_at__isnull=True)
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
    queryset = Mapi.objects.filter(deleted_at__isnull=True)
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
    queryset = VaccineExt.objects.filter(deleted_at__isnull=True)
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
        return Vaccination.objects.filter(patient__code_patient=code_patient, deleted_at__isnull=True)


class PatientMapisListView(generics.ListAPIView):
    """Liste des MAPI d'un patient"""
    serializer_class = MapiSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        code_patient = self.kwargs['code_patient']
        return Mapi.objects.filter(patient__code_patient=code_patient, deleted_at__isnull=True)


class PatientVaccineExtsListView(generics.ListAPIView):
    """Liste des vaccins externes d'un patient"""
    serializer_class = VaccineExtSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        code_patient = self.kwargs['code_patient']
        return VaccineExt.objects.filter(patient__code_patient=code_patient, deleted_at__isnull=True)