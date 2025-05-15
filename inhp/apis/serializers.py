from rest_framework import serializers

from inhp.models import Utilisateur, Patient, Vaccin, Mapi, VaccineExt, Vaccination


class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'role', 'centre', 'district', 'region', 'pole',
                  'access_level', 'is_active']


# class PatientSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Patient
#         fields = ['id', 'code_patient', 'nom', 'prenoms', 'email', 'date_naissance', 'sexe', 'telephone1', 'telephone2',
#                   'centre']

class VaccinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccin
        fields = '__all__'


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'deleted_at', 'code_patient')
        extra_kwargs = {
            'code_otp': {'write_only': True},
            'user_permissions': {'read_only': True},
            'groups': {'read_only': True},
        }


class MapiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mapi
        fields = '__all__'


class VaccinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccination
        fields = '__all__'


class VaccineExtSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccineExt
        fields = '__all__'
