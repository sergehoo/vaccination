from datetime import timezone

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis.admin import GISModelAdmin
from django.contrib.gis.geos import Point
from django.shortcuts import render
from django.urls import reverse, path
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ImportExportModelAdmin, ImportExportMixin
from django.contrib.gis.admin import GISModelAdmin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin, ImportExportMixin
from import_export.widgets import ForeignKeyWidget
from .models import HealthRegion, DistrictSanitaire, PolesRegionaux
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    PolesRegionaux, HealthRegion, DistrictSanitaire, TypeServiceSanitaire,
    CentreVaccination, Utilisateur, Patient, Vaccin, Vaccination, Maladie, LotVaccin, TemplateConsultation,
    Consultation, Mapi, Message, VaccineExt, Equipement, FactureCentral, FactureDistrict, FactureRegion, Facture,
    FatureParametre, FicheRetro, CallCenter
)
from django.utils.translation import gettext_lazy as _

# 🔹 Ajout de modèles basiques
# admin.site.register(PolesRegionaux)
# admin.site.register(HealthRegion)
# admin.site.register(DistrictSanitaire)
admin.site.register(TypeServiceSanitaire)


# Resource pour l'import/export
class PolesRegionauxResource(resources.ModelResource):
    class Meta:
        model = PolesRegionaux
        skip_unchanged = True
        report_skipped = True
        exclude = ('id',)
        import_id_fields = ('name',)
        # Pour l'import en masse
        use_bulk = True


# Admin class avec import/export
@admin.register(PolesRegionaux)
class PolesRegionauxAdmin(ImportExportModelAdmin):
    resource_class = PolesRegionauxResource
    # Configuration de l'interface liste
    list_display = ['name']
    list_display_links = ['name']
    search_fields = ['name']
    ordering = ['name']


class HealthRegionResource(resources.ModelResource):
    poles = fields.Field(
        column_name='poles',
        attribute='poles',
        widget=ForeignKeyWidget(PolesRegionaux, 'name')
    )

    class Meta:
        model = HealthRegion
        skip_unchanged = True
        report_skipped = True
        exclude = ('id',)
        import_id_fields = ('name',)
        use_bulk = True
        fields = ('name', 'poles')

    def get_or_init_instance(self, instance_loader, row):
        """Gérer les doublons lors de l'import"""
        instance, created = super().get_or_init_instance(instance_loader, row)
        return instance, created


class DistrictSanitaireResource(resources.ModelResource):
    region = fields.Field(
        column_name='region',
        attribute='region',
        widget=ForeignKeyWidget(HealthRegion, 'name')
    )

    poles = fields.Field(
        column_name='poles',
        attribute='region__poles',
        widget=ForeignKeyWidget(PolesRegionaux, 'name'),
        readonly=True
    )

    class Meta:
        model = DistrictSanitaire
        skip_unchanged = True
        report_skipped = True
        exclude = ('id', 'geom', 'geojson')
        import_id_fields = ('nom',)
        use_bulk = True
        fields = ('nom', 'region', 'poles')

    def before_save_instance(self, instance, using_transactions, dry_run):
        """Validation avant sauvegarde"""
        if not instance.nom:
            raise ValueError("Le nom du district ne peut pas être vide")
        if not instance.region:
            raise ValueError("La région sanitaire doit être spécifiée")


# Admin classes
@admin.register(HealthRegion)
class HealthRegionAdmin(ImportExportModelAdmin):
    resource_class = HealthRegionResource

    # Configuration de l'interface liste
    list_display = ['name', 'poles', 'get_districts_count']
    list_display_links = ['name']
    list_filter = ['poles']
    search_fields = ['name', 'poles__name']
    list_select_related = ['poles']
    ordering = ['name']
    list_per_page = 50

    # Champs pour l'édition
    fields = ['name', 'poles']
    autocomplete_fields = ['poles']

    def get_districts_count(self, obj):
        """Affiche le nombre de districts dans cette région"""
        count = obj.districts.count()
        return f"{count} district(s)"

    get_districts_count.short_description = "Districts"
    get_districts_count.admin_order_field = 'districts__count'

    def get_CentreVaccination_count(self, obj):
        """Affiche le nombre d'églises dans cette région (via les districts)"""
        from django.db.models import Count
        count = DistrictSanitaire.objects.filter(region=obj).aggregate(
            total=Count('CentreVaccination')
        )['total'] or 0
        return f"{count} Centre Vaccination(s)"

    get_CentreVaccination_count.short_description = "Centre Vaccination"


@admin.register(DistrictSanitaire)
class DistrictSanitaireAdmin(ImportExportMixin, GISModelAdmin):
    resource_class = DistrictSanitaireResource

    # Configuration de l'interface liste
    list_display = ['nom', 'region', 'get_pole', 'get_CentreVaccination_count', 'has_geometry']
    list_display_links = ['nom']
    list_filter = ['region', 'region__poles']
    search_fields = ['nom', 'region__name', 'region__poles__name']
    list_select_related = ['region', 'region__poles']
    ordering = ['nom']
    list_per_page = 50

    # Champs pour l'édition
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom', 'region')
        }),
        ('Géométrie', {
            'fields': ('geom', 'geojson'),
            'classes': ('collapse',)
        }),
    )

    autocomplete_fields = ['region']

    # Configuration GIS
    gis_widget_kwargs = {
        'attrs': {
            'default_lat': 7.5399,  # Côte d'Ivoire
            'default_lon': -5.5471,
            'default_zoom': 7,
        }
    }

    def get_pole(self, obj):
        """Affiche le pôle régional associé"""
        return obj.region.poles if obj.region and obj.region.poles else "-"

    get_pole.short_description = "Pôle Régional"
    get_pole.admin_order_field = 'region__poles__name'

    def get_CentreVaccination_count(self, obj):
        """Affiche le nombre d'églises dans ce district"""
        count = obj.centres.count()  # Supposant la relation inverse
        return f"{count} centres(s)"

    get_CentreVaccination_count.short_description = "Centres de vaccination"
    get_CentreVaccination_count.admin_order_field = 'CentreVaccination__count'

    def has_geometry(self, obj):
        """Indique si le district a une géométrie"""
        return bool(obj.geom)

    has_geometry.boolean = True
    has_geometry.short_description = "Avec géo"

    # Actions personnalisées
    actions = ['generate_geojson_from_geom']

    def generate_geojson_from_geom(self, request, queryset):
        """Générer le GeoJSON à partir de la géométrie"""
        from django.contrib.gis.geos import GEOSGeometry
        updated = 0
        for district in queryset:
            if district.geom and not district.geojson:
                try:
                    district.geojson = GEOSGeometry(district.geom.geojson)
                    district.save(update_fields=['geojson'])
                    updated += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Erreur pour {district.nom}: {e}",
                        level='ERROR'
                    )

        self.message_user(
            request,
            f"GeoJSON généré pour {updated} district(s)",
            level='SUCCESS'
        )

    generate_geojson_from_geom.short_description = "Générer GeoJSON depuis la géométrie"

    def get_export_queryset(self, request):
        """Optimiser le queryset d'export"""
        return super().get_export_queryset(request).select_related(
            'region', 'region__poles'
        )


# Alternative avec des fonctionnalités avancées
class DistrictSanitaireInline(admin.TabularInline):
    model = DistrictSanitaire
    extra = 0
    fields = ['nom', 'has_geometry']
    readonly_fields = ['has_geometry']

    def has_geometry(self, obj):
        return bool(obj.geom)

    has_geometry.boolean = True
    has_geometry.short_description = "Géo"


class HealthRegionAdminWithInline(HealthRegionAdmin):
    inlines = [DistrictSanitaireInline]
    list_display = ['name', 'poles', 'get_districts_count', 'get_CentreVaccination_count']


class CentreVaccinationResource(resources.ModelResource):
    type = fields.Field(
        column_name='type',
        attribute='type',
        widget=ForeignKeyWidget(TypeServiceSanitaire, 'name')
    )

    district = fields.Field(
        column_name='district',
        attribute='district',
        widget=ForeignKeyWidget(DistrictSanitaire, 'nom')
    )

    region = fields.Field(
        column_name='region',
        attribute='district__region',
        widget=ForeignKeyWidget(HealthRegion, 'name'),
        readonly=True
    )

    poles = fields.Field(
        column_name='poles',
        attribute='district__region__poles',
        widget=ForeignKeyWidget(PolesRegionaux, 'name'),
        readonly=True
    )

    class Meta:
        model = CentreVaccination
        skip_unchanged = True
        report_skipped = True
        exclude = ('id', 'geom', 'deleted_at')
        import_id_fields = ('name',)
        use_bulk = True
        fields = ('name', 'type', 'longitude', 'latitude', 'district', 'adresse', 'region', 'poles')

    def after_import_instance(self, instance, new, **kwargs):
        """Post-traitement après l'import"""
        # S'assurer que la géométrie est à jour
        if instance.longitude and instance.latitude and not instance.geom:
            try:
                instance.geom = Point(float(instance.longitude), float(instance.latitude))
            except (ValueError, TypeError):
                pass  # Ignorer les erreurs de conversion


# Admin class
@admin.register(CentreVaccination)
class CentreVaccinationAdmin(ImportExportMixin, GISModelAdmin):
    resource_class = CentreVaccinationResource

    # Configuration de l'interface liste
    list_display = [
        'name',
        'type',
        'district',
        'get_region',
        'get_pole',
        'has_coordinates',
        'has_geometry',
        'created_at'
    ]

    list_display_links = ['name']
    list_filter = [
        'type',
        'district',
        'district__region',
        'district__region__poles',
        'created_at'
    ]

    search_fields = [
        'name',
        'adresse',
        'district__nom',
        'district__region__name',
        'type__name'
    ]

    list_select_related = [
        'type',
        'district',
        'district__region',
        'district__region__poles'
    ]

    ordering = ['name']
    list_per_page = 50
    date_hierarchy = 'created_at'

    # Champs pour l'édition
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'type', 'district', 'adresse')
        }),
        ('Localisation', {
            'fields': ('latitude', 'longitude', 'geom'),
            'description': 'Renseignez soit les coordonnées manuellement, soit la géométrie sur la carte'
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']
    # autocomplete_fields = ['type', 'district']

    # Configuration GIS
    gis_widget_kwargs = {
        'attrs': {
            'default_lat': 7.5399,  # Côte d'Ivoire
            'default_lon': -5.5471,
            'default_zoom': 7,
            'map_width': 800,
            'map_height': 500,
        }
    }

    # Méthodes pour l'affichage
    def get_region(self, obj):
        """Affiche la région sanitaire"""
        return obj.district.region if obj.district and obj.district.region else "-"

    get_region.short_description = "Région"
    get_region.admin_order_field = 'district__region__name'

    def get_pole(self, obj):
        """Affiche le pôle régional"""
        return obj.district.region.poles if obj.district and obj.district.region and obj.district.region.poles else "-"

    get_pole.short_description = "Pôle"
    get_pole.admin_order_field = 'district__region__poles__name'

    def has_coordinates(self, obj):
        """Indique si le centre a des coordonnées"""
        return bool(obj.latitude and obj.longitude)

    has_coordinates.boolean = True
    has_coordinates.short_description = "Coords"

    def has_geometry(self, obj):
        """Indique si le centre a une géométrie"""
        return bool(obj.geom)

    has_geometry.boolean = True
    has_geometry.short_description = "Géo"

    # Actions personnalisées
    actions = [
        'generate_geom_from_coords',
        'generate_coords_from_geom',
        'update_geojson_data'
    ]

    def generate_geom_from_coords(self, request, queryset):
        """Générer la géométrie à partir des coordonnées"""
        updated = 0
        for centre in queryset:
            if centre.latitude and centre.longitude and not centre.geom:
                try:
                    centre.geom = Point(float(centre.longitude), float(centre.latitude))
                    centre.save(update_fields=['geom'])
                    updated += 1
                except (ValueError, TypeError) as e:
                    self.message_user(
                        request,
                        f"Erreur pour {centre.name}: {e}",
                        level='ERROR'
                    )

        self.message_user(
            request,
            f"Géométrie générée pour {updated} centre(s)",
            level='SUCCESS'
        )

    generate_geom_from_coords.short_description = "Générer la géométrie depuis les coordonnées"

    def generate_coords_from_geom(self, request, queryset):
        """Générer les coordonnées à partir de la géométrie"""
        updated = 0
        for centre in queryset:
            if centre.geom and (not centre.longitude or not centre.latitude):
                try:
                    centre.longitude = centre.geom.x
                    centre.latitude = centre.geom.y
                    centre.save(update_fields=['longitude', 'latitude'])
                    updated += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Erreur pour {centre.name}: {e}",
                        level='ERROR'
                    )

        self.message_user(
            request,
            f"Coordonnées générées pour {updated} centre(s)",
            level='SUCCESS'
        )

    generate_coords_from_geom.short_description = "Générer les coordonnées depuis la géométrie"

    def update_geojson_data(self, request, queryset):
        """Mettre à jour les données GeoJSON (si vous avez un champ geojson)"""
        updated = 0
        for centre in queryset:
            if centre.geom:
                try:
                    # Si vous avez un champ geojson dans votre modèle
                    # centre.geojson = centre.geom.geojson
                    centre.save()
                    updated += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Erreur pour {centre.name}: {e}",
                        level='ERROR'
                    )

        self.message_user(
            request,
            f"Données GeoJSON mises à jour pour {updated} centre(s)",
            level='SUCCESS'
        )

    update_geojson_data.short_description = "Mettre à jour les données GeoJSON"

    # Surcharge des méthodes de sauvegarde
    def save_model(self, request, obj, form, change):
        """S'assurer que la géométrie est synchronisée avec les coordonnées"""
        if obj.latitude and obj.longitude and not obj.geom:
            try:
                obj.geom = Point(float(obj.longitude), float(obj.latitude))
            except (ValueError, TypeError):
                pass  # Garder la géométrie existante si conversion échoue

        super().save_model(request, obj, form, change)

    # Configuration des permissions
    def has_import_permission(self, request):
        return request.user.has_perm('your_app.import_centrevaccination')

    def has_export_permission(self, request):
        return request.user.has_perm('your_app.export_centrevaccination')

    def get_export_queryset(self, request):
        """Optimiser le queryset d'export"""
        return super().get_export_queryset(request).select_related(
            'type',
            'district',
            'district__region',
            'district__region__poles'
        )


# Inline pour afficher les centres dans le district
class CentreVaccinationInline(admin.TabularInline):
    model = CentreVaccination
    extra = 0
    fields = ['name', 'type', 'has_coordinates', 'has_geometry']
    readonly_fields = ['has_coordinates', 'has_geometry']
    show_change_link = True

    def has_coordinates(self, obj):
        return bool(obj.latitude and obj.longitude)

    has_coordinates.boolean = True
    has_coordinates.short_description = "Coords"

    def has_geometry(self, obj):
        return bool(obj.geom)

    has_geometry.boolean = True
    has_geometry.short_description = "Géo"


class UtilisateurCreationForm(forms.ModelForm):
    """
    Formulaire utilisé dans l'admin pour créer un utilisateur.
    Gère password1/password2 + hash.
    """
    password1 = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label=_("Confirmation du mot de passe"),
        widget=forms.PasswordInput,
    )

    class Meta:
        model = Utilisateur
        fields = ("email", "first_name", "last_name")

    def clean_password2(self):
        pwd1 = self.cleaned_data.get("password1")
        pwd2 = self.cleaned_data.get("password2")
        if pwd1 and pwd2 and pwd1 != pwd2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        return pwd2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UtilisateurChangeForm(forms.ModelForm):
    """
    Formulaire de modification (on laisse Django gérer la zone password).
    """

    class Meta:
        model = Utilisateur
        fields = "__all__"


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    add_form = UtilisateurCreationForm
    form = UtilisateurChangeForm
    model = Utilisateur

    list_display = ("email", "first_name", "last_name", "role", "access_level", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "role", "access_level")

    ordering = ("email",)
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (_("Identité"), {"fields": ("email", "first_name", "last_name", "phone")}),
        (_("Affectation"), {"fields": ("centre", "district", "region", "pole", "access_level", "role")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Infos sécurité"), {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (_("Compte"), {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2"),
        }),
        (_("Affectation"), {
            "classes": ("wide",),
            "fields": ("centre", "district", "region", "pole", "access_level", "role"),
        }),
        (_("Permissions"), {
            "classes": ("wide",),
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
    )


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
