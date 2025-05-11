from rest_framework import serializers

from inhp.models import Utilisateur, Patient, Vaccin


class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'role', 'centre', 'district', 'region', 'pole',
                  'access_level', 'is_active']


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'code_patient', 'nom', 'prenoms', 'email', 'date_naissance', 'sexe', 'telephone1', 'telephone2',
                  'centre']

class VaccinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccin
        fields = '__all__'