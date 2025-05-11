from rest_framework import viewsets, permissions

from inhp.apis.serializers import UtilisateurSerializer, PatientSerializer, VaccinSerializer
from inhp.models import Utilisateur, Patient, CentreBasedPermission, Vaccin


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