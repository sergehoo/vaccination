from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html

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
class PatientAdmin(UserAdmin):
    """Configuration d'administration pour le modèle Patient"""

    # Configuration de base
    list_display = [
        'code_patient',
        'nom_complet',
        'age',
        'sexe',
        'telephone1',
        'commune',
        'statut_display',
        'is_active',
        'account_status',
        'created_at'
    ]

    list_filter = [
        'sexe',
        'statut',
        'is_active',
        'commune',
        'niveau_instruction',
        'situation_matrimoniale',
        'centre',
        'created_at',
        'must_change_password',
        ('account_locked_until', admin.EmptyFieldListFilter),
    ]

    search_fields = [
        'code_patient',
        'nom',
        'prenoms',
        'telephone1',
        'telephone2',
        'email',
        'num_piece',
        'commune',
        'quartier'
    ]

    readonly_fields = [
        'age_display',
        'account_status',
        'last_login_display',
        'created_at',
        'updated_at',
        'failed_login_attempts_display',
        'password_change_required',
        'vaccinations_count'
    ]

    fieldsets = (
        ('Informations d\'identification', {
            'fields': (
                'code_patient',
                'email',

            )
        }),
        ('Informations personnelles', {
            'fields': (
                'nom',
                'prenoms',
                'date_naissance',
                'age_display',
                'sexe',
                'situation_matrimoniale',
                'nombre_enfant',
                'nationalite'
            )
        }),
        ('Pièce d\'identité', {
            'fields': (
                'type_piece',
                'num_piece'
            )
        }),
        ('Coordonnées', {
            'fields': (
                'telephone1',
                'telephone2',
                'commune',
                'quartier'
            )
        }),
        ('Situation socio-professionnelle', {
            'fields': (
                'niveau_instruction',
                'profession'
            )
        }),
        ('Sécurité et accès', {
            'fields': (
                'is_active',
                'account_status',
                'failed_login_attempts_display',
                'last_login_display',
                'last_failed_login',
                'account_locked_until',
                'must_change_password',
                'password_change_required',
                'statut'
            )
        }),
        ('Centre de vaccination', {
            'fields': (
                'centre',
                'centre_actuel',
                'consentement_parental',
                'vaccinations_count'
            )
        }),
        ('Permissions', {
            'fields': (
                'groups',
                'user_permissions'
            )
        }),
        ('Métadonnées', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'code_patient',
                'email',
                'nom',
                'prenoms',
                'date_naissance',
                'sexe',
                'telephone1',
                'password1',
                'password2'
            ),
        }),
    )

    ordering = ['-created_at', 'nom', 'prenoms']
    date_hierarchy = 'created_at'
    filter_horizontal = ['groups', 'user_permissions']
    actions = [
        'activate_patients',
        'deactivate_patients',
        'reset_login_attempts',
        'unlock_accounts',
        'force_password_change'
    ]

    # Méthodes d'affichage personnalisées
    def nom_complet(self, obj):
        return f"{obj.nom} {obj.prenoms}"

    nom_complet.short_description = "Nom complet"
    nom_complet.admin_order_field = 'nom'

    def age_display(self, obj):
        if obj.age is not None:
            return f"{obj.age} ans"
        return "Non spécifié"

    age_display.short_description = "Âge"

    def statut_display(self, obj):
        color = "green" if obj.statut == "actif" else "red"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_display()
        )

    statut_display.short_description = "Statut"

    def account_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: red; font-weight: bold;">❌ Compte désactivé</span>')

        if obj.is_account_locked():
            return format_html(
                '<span style="color: orange; font-weight: bold;">🔒 Compte verrouillé</span>'
            )

        if obj.failed_login_attempts > 0:
            return format_html(
                '<span style="color: orange;">⚠️ {} tentatives échouées</span>',
                obj.failed_login_attempts
            )

        return format_html('<span style="color: green; font-weight: bold;">✅ Actif</span>')

    account_status.short_description = "État du compte"

    def failed_login_attempts_display(self, obj):
        if obj.failed_login_attempts > 0:
            color = "red" if obj.failed_login_attempts >= 3 else "orange"
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} tentative(s)</span>',
                color,
                obj.failed_login_attempts
            )
        return format_html('<span style="color: green;">Aucune</span>')

    failed_login_attempts_display.short_description = "Tentatives échouées"

    def last_login_display(self, obj):
        if obj.last_login:
            return obj.last_login.strftime("%d/%m/%Y %H:%M")
        return "Jamais connecté"

    last_login_display.short_description = "Dernière connexion"

    # def password_display(self, obj):
    #     return format_html(
    #         '<a href="{}" style="background: #417690; color: white; padding: 5px 10px; '
    #         'text-decoration: none; border-radius: 3px;">Changer le mot de passe</a>',
    #         reverse('admin:auth_user_password_change', args=[obj.pk])
    #     )

    # password_display.short_description = "Mot de passe"

    def password_change_required(self, obj):
        if obj.must_change_password:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Changement requis</span>')
        return format_html('<span style="color: green;">✅ À jour</span>')

    password_change_required.short_description = "Mot de passe"

    def vaccinations_count(self, obj):
        count = obj.vaccination_set.count()
        url = reverse('admin:inhp_vaccination_changelist') + f'?patient__id__exact={obj.id}'
        return format_html(
            '<a href="{}" style="background: #4CAF50; color: white; padding: 3px 8px; '
            'text-decoration: none; border-radius: 3px;">{} vaccination(s)</a>',
            url, count
        )

    vaccinations_count.short_description = "Vaccinations"

    # Actions personnalisées
    def activate_patients(self, request, queryset):
        updated = queryset.update(is_active=True, failed_login_attempts=0, account_locked_until=None)
        self.message_user(
            request,
            f"{updated} patient(s) activé(s) avec succès."
        )

    activate_patients.short_description = "Activer les patients sélectionnés"

    def deactivate_patients(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} patient(s) désactivé(s) avec succès."
        )

    deactivate_patients.short_description = "Désactiver les patients sélectionnés"

    def reset_login_attempts(self, request, queryset):
        updated = queryset.update(failed_login_attempts=0, account_locked_until=None)
        self.message_user(
            request,
            f"Compteurs de tentatives réinitialisés pour {updated} patient(s)."
        )

    reset_login_attempts.short_description = "Réinitialiser les tentatives de connexion"

    def unlock_accounts(self, request, queryset):
        updated = queryset.update(account_locked_until=None, failed_login_attempts=0)
        self.message_user(
            request,
            f"{updated} compte(s) déverrouillé(s) avec succès."
        )

    unlock_accounts.short_description = "Déverrouiller les comptes"

    def force_password_change(self, request, queryset):
        updated = queryset.update(must_change_password=True)
        self.message_user(
            request,
            f"{updated} patient(s) devront changer leur mot de passe à la prochaine connexion."
        )

    force_password_change.short_description = "Forcer le changement de mot de passe"

    # Méthodes de sauvegarde
    def save_model(self, request, obj, form, change):
        if not change:  # Création d'un nouveau patient
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # Permissions
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Filtrage personnalisé selon les permissions
        if request.user.is_superuser:
            return qs
        return qs

    # Configuration des permissions dans l'admin
    def has_module_permission(self, request):
        return request.user.has_perm('inhp.view_patient')

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('inhp.view_patient')

    def has_add_permission(self, request):
        return request.user.has_perm('inhp.add_patient')

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('inhp.change_patient')

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('inhp.delete_patient')


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
