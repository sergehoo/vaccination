from django.contrib import admin

from .models import (
    PolesRegionaux, HealthRegion, DistrictSanitaire, TypeServiceSanitaire,
    CentreVaccination, Utilisateur, Patient, Vaccin, Vaccination, Maladie, LotVaccin, TemplateConsultation,
    Consultation, Mapi, Message, VaccineExt, Equipement, FactureCentral, FactureDistrict, FactureRegion, Facture,
    FatureParametre, FicheRetro, CallCenter
)

# 🔹 Ajout de modèles basiques
admin.site.register(PolesRegionaux)
admin.site.register(HealthRegion)
admin.site.register(DistrictSanitaire)
admin.site.register(TypeServiceSanitaire)


# 🔹 Ajout avec personnalisation
@admin.register(CentreVaccination)
class CentreVaccinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'district', 'created_at')
    search_fields = ('name', 'district__nom')
    # autocomplete_fields = ('type', 'district','name')


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'centre', 'access_level', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('role', 'access_level', 'is_active')
    # autocomplete_fields = ('centre', 'access_level','first_name')


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('code_patient', 'nom', 'prenoms', 'sexe', 'num_piece', 'telephone1', 'centre', 'statut')
    search_fields = ('code_patient', 'nom', 'prenoms', 'telephone1')
    list_filter = ('sexe', 'statut')
    # autocomplete_fields = ['code_patient']


@admin.register(Vaccination)
class VaccinationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'vaccin', 'dose', 'date_vaccination')
    search_fields = ('patient__nom', 'vaccin__nom')
    list_filter = ('vaccin', 'date_vaccination')
    # raw_id_fields = ('patient', 'vaccin')
    autocomplete_fields = ['patient']


@admin.register(Maladie)
class MaladieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    list_filter = ['nom']


@admin.register(LotVaccin)
class LotVaccinAdmin(admin.ModelAdmin):
    list_display = (
        'numero_lot',
        'vaccin',
        'centre',
        'quantite_initiale',
        'quantite_disponible',
        'date_expiration',
    )
    list_filter = ('vaccin', 'centre', 'date_expiration')
    search_fields = ('numero_lot', 'vaccin__nom', 'centre__name')
    # autocomplete_fields = ('vaccin', 'centre')
    ordering = ('-updated_at',)


@admin.register(TemplateConsultation)
class TemplateConsultationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)


@admin.register(Vaccin)
class VaccinAdmin(admin.ModelAdmin):
    list_display = ('nom', 'fabricant', 'type_vaccin', 'doses_requises', 'statut_approbation')
    search_fields = ('nom', 'fabricant')
    list_filter = ('type_vaccin', 'statut_approbation')


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'centre', 'maladie', 'created_at')
    list_filter = ('centre', 'maladie', 'created_at')


@admin.register(Mapi)
class MapiAdmin(admin.ModelAdmin):
    list_display = ('patient', 'centre', 'date')
    list_filter = ('centre', 'date')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('message', 'type', 'is_active', 'utilisateur')
    list_filter = ('type', 'is_active')
    search_fields = ('message',)


@admin.register(VaccineExt)
class VaccineExtAdmin(admin.ModelAdmin):
    list_display = ('patient', 'vaccin', 'pays', 'ville', 'date')
    list_filter = ('pays', 'ville')
    search_fields = ('patient__nom',)


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ('type', 'marque', 'numero_serie', 'centre')
    list_filter = ('type', 'centre')


@admin.register(FactureCentral)
class FactureCentralAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'total', 'created_by', 'date_debut', 'date_fin')


@admin.register(FactureDistrict)
class FactureDistrictAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'district', 'total', 'bonus', 'total_centre')


@admin.register(FactureRegion)
class FactureRegionAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'region', 'total', 'total_centre')


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'centre', 'total', 'nbre_vaccine', 'bonus')


@admin.register(FatureParametre)
class FatureParametreAdmin(admin.ModelAdmin):
    list_display = ('prix_unitaire',)


@admin.register(FicheRetro)
class FicheRetroAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'date_naissance', 'sexe', 'telephone1', 'is_valider')
    search_fields = ('nom', 'prenoms', 'telephone1')
    list_filter = ('sexe', 'is_valider', 'date_naissance')


@admin.register(CallCenter)
class CallCenterAdmin(admin.ModelAdmin):
    list_display = ('telephone', 'disponible')
    list_filter = ('disponible',)
