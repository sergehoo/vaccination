from dateutil.relativedelta import relativedelta
from rest_framework import serializers

from inhp.models import Utilisateur, Patient, Vaccin, Mapi, VaccineExt, Vaccination, FicheRetro, CentreVaccination, \
    LotVaccin


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
    centre = serializers.StringRelatedField(read_only=True)
    centre_actuel = serializers.StringRelatedField(read_only=True)

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


class FicheRetroSerializer(serializers.ModelSerializer):
    class Meta:
        model = FicheRetro
        fields = '__all__'


class CentreVaccinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CentreVaccination
        fields = ['id', 'nom', 'adresse', 'ville', 'telephone']


class LotVaccinSerializer(serializers.ModelSerializer):
    vaccin_nom = serializers.CharField(source='vaccin.nom', read_only=True)

    class Meta:
        model = LotVaccin
        fields = ['id', 'numero_lot', 'vaccin', 'vaccin_nom', 'date_expiration', 'stock']


class VaccinationListSerializer(serializers.ModelSerializer):
    patient_nom = serializers.CharField(source='patient.nom', read_only=True)
    patient_prenoms = serializers.CharField(source='patient.prenoms', read_only=True)
    centre_nom = serializers.CharField(source='centre.nom', read_only=True)
    vaccin_nom = serializers.CharField(source='vaccin.nom', read_only=True)
    lot_numero = serializers.CharField(source='lot.numero_lot', read_only=True)
    created_by_nom = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Vaccination
        fields = [
            'id', 'patient', 'patient_nom', 'patient_prenoms', 'centre', 'centre_nom',
            'date_vaccination', 'vaccin', 'vaccin_nom', 'lot', 'lot_numero', 'dose',
            'date_rappel', 'created_by', 'created_by_nom', 'created_at', 'updated_at'
        ]


class VaccinationDetailSerializer(serializers.ModelSerializer):
    patient_details = PatientSerializer(source='patient', read_only=True)
    centre_details = CentreVaccinationSerializer(source='centre', read_only=True)
    vaccin_details = VaccinSerializer(source='vaccin', read_only=True)
    lot_details = LotVaccinSerializer(source='lot', read_only=True)
    created_by_details = UtilisateurSerializer(source='created_by', read_only=True)
    jours_restants_rappel = serializers.SerializerMethodField()

    class Meta:
        model = Vaccination
        fields = [
            'id', 'patient', 'patient_details', 'centre', 'centre_details',
            'date_vaccination', 'vaccin', 'vaccin_details', 'lot', 'lot_details',
            'dose', 'date_rappel', 'jours_restants_rappel', 'created_by',
            'created_by_details', 'created_at', 'updated_at', 'deleted_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'deleted_at']

    def get_jours_restants_rappel(self, obj):
        if obj.date_rappel:
            from datetime import date
            today = date.today()
            jours_restants = (obj.date_rappel - today).days
            return max(jours_restants, 0)
        return None


class VaccinationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccination
        fields = [
            'patient', 'centre', 'date_vaccination', 'vaccin', 'lot',
            'dose', 'date_rappel', 'created_by'
        ]

    def validate(self, data):
        # Validation de la dose
        if data.get('dose') <= 0:
            raise serializers.ValidationError("La dose doit être un nombre positif")

        # Validation de la date de vaccination
        from datetime import date
        if data.get('date_vaccination') > date.today():
            raise serializers.ValidationError("La date de vaccination ne peut pas être dans le futur")

        # Validation du stock du lot
        lot = data.get('lot')
        if lot and lot.stock <= 0:
            raise serializers.ValidationError("Le lot sélectionné n'a plus de stock disponible")

        # Validation patient déjà vacciné avec la même dose
        patient = data.get('patient')
        vaccin = data.get('vaccin')
        dose = data.get('dose')

        if patient and vaccin and dose:
            existing_vaccination = Vaccination.objects.filter(
                patient=patient,
                vaccin=vaccin,
                dose=dose,
                deleted_at__isnull=True
            ).exists()

            if existing_vaccination:
                raise serializers.ValidationError(
                    f"Ce patient a déjà reçu la dose {dose} de ce vaccin"
                )

        return data

    def create(self, validated_data):
        # Calcul automatique de la date de rappel si non fournie
        if not validated_data.get('date_rappel') and validated_data.get('vaccin'):
            vaccin = validated_data['vaccin']
            if vaccin.besoin_rappel and vaccin.duree_immunite:
                date_vaccination = validated_data['date_vaccination']
                validated_data['date_rappel'] = date_vaccination + relativedelta(months=vaccin.duree_immunite)

        # Déduire le stock du lot
        lot = validated_data.get('lot')
        if lot and lot.stock > 0:
            lot.stock -= 1
            lot.save()

        return super().create(validated_data)


class VaccinationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccination
        fields = [
            'patient', 'centre', 'date_vaccination', 'vaccin', 'lot',
            'dose', 'date_rappel'
        ]

    def validate(self, data):
        # Réutiliser les validations du create serializer
        return VaccinationCreateSerializer.validate(self, data)

    def update(self, instance, validated_data):
        # Gestion du stock lors de la modification du lot
        old_lot = instance.lot
        new_lot = validated_data.get('lot')

        if old_lot and old_lot != new_lot:
            # Réapprovisionner l'ancien lot
            old_lot.stock += 1
            old_lot.save()

            # Déduire le nouveau lot
            if new_lot and new_lot.stock > 0:
                new_lot.stock -= 1
                new_lot.save()

        return super().update(instance, validated_data)
