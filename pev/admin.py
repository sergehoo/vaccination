# vaccination/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils import timezone

from .models import PEVCampaign, PEVCampaignTeam
from inhp.models import (
    ServiceVaccination,
    Vaccin,
    HealthRegion,
    PolesRegionaux,
    DistrictSanitaire,
    CentreVaccination,
)


# ==============================
#  PEVCampaignAdmin
# ==============================

@admin.register(PEVCampaign)
class PEVCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'nom_court', 'type_campagne', 'statut',
        'date_debut', 'date_fin', 'progression_display',
        'couverture_display', 'efficacite_display', 'row_actions'
    ]

    list_filter = [
        'statut', 'type_campagne', 'frequence', 'actif',
        'date_debut', 'date_fin', 'service'
    ]

    search_fields = [
        'code', 'nom', 'nom_court', 'description'
    ]

    readonly_fields = [
        'date_creation', 'date_modification', 'progression_temps',
        'progression_couverture', 'efficacite_campagne', 'jours_restants',
        'budget_utilise', 'taux_couverture_reel', 'taux_effets_secondaires',
        'couverture_display_field',
    ]

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'service', 'code', 'nom', 'nom_court',
                'type_campagne', 'frequence', 'statut', 'actif'
            )
        }),
        ('Période', {
            'fields': (
                'date_debut', 'date_fin',
                'date_debut_reelle', 'date_fin_reelle',
                'jours_restants', 'progression_temps'
            )
        }),
        ('Description et objectifs', {
            'fields': ('description', 'objectifs')
        }),
        ('Cible de vaccination', {
            'fields': (
                'age_min_mois', 'age_max_mois',
                'population_cible', 'couverture_cible',
                'couverture_display_field', 'progression_couverture'
            )
        }),
        ('Vaccins et territoires', {
            'fields': (
                'vaccins', 'poles', 'regions', 'districts', 'centres'
            )
        }),
        ('Budget et ressources', {
            'fields': (
                'budget_alloue', 'budget_depense', 'budget_utilise',
                'equipes_mobiles', 'personnel_implique','remuneration_mode','montant_par_vaccination'
            )
        }),
        ('Indicateurs de performance', {
            'fields': (
                'nombre_enfants_vaccines', 'doses_administrees',
                'taux_couverture_reel', 'incidents_signales',
                'taux_effets_secondaires', 'efficacite_campagne'
            )
        }),
        ('Logistique et communication', {
            'fields': (
                'statut_approvisionnement', 'besoin_logistique',
                'plan_communication', 'partenaires_impliques'
            )
        }),
        ('Responsables', {
            'fields': ('created_by', 'responsable_campagne')
        }),
        ('Métadonnées', {
            'fields': (
                'date_creation', 'date_modification', 'meta'
            ),
            'classes': ('collapse',)
        })
    )

    filter_horizontal = ['vaccins', 'poles', 'regions', 'districts', 'centres']

    # ✅ Bulk actions Django
    actions = ['activer_campagnes', 'desactiver_campagnes', 'clore_campagnes']


    def progression_display(self, obj):
        """Affiche la progression temporelle avec une barre de progression."""
        progression = obj.progression_temps
        color = 'green' if progression < 80 else 'orange' if progression < 100 else 'red'
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background: {}; color: white; text-align: center; '
            'border-radius: 3px; font-size: 11px; padding: 2px;">{}%</div>'
            '</div>',
            progression, color, int(progression)
        )

    progression_display.short_description = 'Progression'

    def couverture_display(self, obj):
        """Affiche la couverture avec indicateur visuel."""
        if obj.taux_couverture_reel:
            taux = float(obj.taux_couverture_reel)
            color = 'red' if taux < 80 else 'orange' if taux < 90 else 'green'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color, taux
            )
        return '-'

    couverture_display.short_description = 'Couverture'

    def efficacite_display(self, obj):
        """Affiche l'efficacité avec indicateur coloré."""
        efficacite = obj.efficacite_campagne
        color = 'red' if efficacite < 50 else 'orange' if efficacite < 75 else 'green'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, efficacite
        )

    efficacite_display.short_description = 'Efficacité'

    def couverture_display_field(self, obj):
        """Champ calculé pour l'admin (détail)."""
        if obj.population_cible and obj.nombre_enfants_vaccines:
            return f"{obj.nombre_enfants_vaccines} / {obj.population_cible} ({obj.taux_couverture_reel}%)"
        return "-"

    couverture_display_field.short_description = "Couverture actuelle"

    # ---------- Colonne Actions (ligne) ----------

    def row_actions(self, obj):
        """
        Boutons d'action rapides affichés dans la liste.
        (Ne pas appeler cette méthode 'actions' pour éviter le conflit
         avec l'attribut actions = [...] des bulk actions.)
        """
        links = []

        if obj.statut == 'planifiee':
            links.append(
                f'<a href="{reverse("admin:pev_pevcampaign_demarrer", args=[obj.pk])}" '
                f'class="button" style="background: #4CAF50; color: white; padding: 5px 10px; '
                f'text-decoration: none; border-radius: 3px; font-size: 12px;">Démarrer</a>'
            )
        elif obj.statut == 'en_cours':
            links.append(
                f'<a href="{reverse("admin:pev_pevcampaign_clore", args=[obj.pk])}" '
                f'class="button" style="background: #f44336; color: white; padding: 5px 10px; '
                f'text-decoration: none; border-radius: 3px; font-size: 12px;">Clôturer</a>'
            )

        # Lien vers les équipes associées
        links.append(
            f'<a href="{reverse("admin:pev_pevcampaignteam_changelist")}'
            f'?campagne__id__exact={obj.pk}" '
            f'class="button" style="background: #2196F3; color: white; padding: 5px 10px; '
            f'text-decoration: none; border-radius: 3px; font-size: 12px;">Équipes</a>'
        )

        return format_html(' '.join(links))

    row_actions.short_description = 'Actions'

    # ---------- Bulk actions ----------

    def activer_campagnes(self, request, queryset):
        queryset.update(actif=True)
        self.message_user(request, f"{queryset.count()} campagnes activées.")

    activer_campagnes.short_description = "Activer les campagnes sélectionnées"

    def desactiver_campagnes(self, request, queryset):
        queryset.update(actif=False)
        self.message_user(request, f"{queryset.count()} campagnes désactivées.")

    desactiver_campagnes.short_description = "Désactiver les campagnes sélectionnées"

    def clore_campagnes(self, request, queryset):
        updated = queryset.filter(statut='en_cours').update(
            statut='cloturee',
            date_fin_reelle=timezone.now().date()
        )
        self.message_user(request, f"{updated} campagnes clôturées.")

    clore_campagnes.short_description = "Clôturer les campagnes en cours"

    # ---------- URLs custom admin ----------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/demarrer/',
                self.admin_site.admin_view(self.demarrer_campagne_view),
                name='pev_pevcampaign_demarrer',
            ),
            path(
                '<int:pk>/clore/',
                self.admin_site.admin_view(self.clore_campagne_view),
                name='pev_pevcampaign_clore',
            ),
        ]
        return custom_urls + urls

    def demarrer_campagne_view(self, request, pk):
        """Vue pour démarrer une campagne."""
        from django.shortcuts import redirect, get_object_or_404
        campagne = get_object_or_404(PEVCampaign, pk=pk)
        if campagne.demarrer_campagne():
            self.message_user(request, f"Campagne {campagne.code} démarrée avec succès.")
        else:
            self.message_user(request, "Impossible de démarrer cette campagne.", level='error')
        return redirect('admin:pev_pevcampaign_changelist')

    def clore_campagne_view(self, request, pk):
        """Vue pour clôturer une campagne."""
        from django.shortcuts import redirect, get_object_or_404
        campagne = get_object_or_404(PEVCampaign, pk=pk)
        if campagne.clore_campagne():
            self.message_user(request, f"Campagne {campagne.code} clôturée avec succès.")
        else:
            self.message_user(request, "Impossible de clôturer cette campagne.", level='error')
        return redirect('admin:pev_pevcampaign_changelist')

    # ---------- Form change extra context ----------

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            campagne = PEVCampaign.objects.get(pk=object_id)
            extra_context['stats_agents'] = campagne.stats_par_agent()[:10]  # Top 10 agents
        return super().changeform_view(request, object_id, form_url, extra_context)


# ==============================
#  PEVCampaignTeamAdmin
# ==============================

@admin.register(PEVCampaignTeam)
class PEVCampaignTeamAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'nom', 'campagne_link', 'type_equipe', 'responsable_link',
        'zone_display', 'enfants_vaccines', 'doses_administrees',
        'performance_display', 'actif', 'row_actions'
    ]

    list_filter = [
        'campagne', 'type_equipe', 'actif', 'pole', 'region', 'district', 'centre'
    ]

    search_fields = [
        'code', 'nom', 'campagne__code', 'campagne__nom',
        'responsable__first_name', 'responsable__last_name'
    ]

    readonly_fields = [
        'date_creation', 'date_modification', 'zone_principale_label',
        'performance_display_field', 'taux_incidents_field'
    ]

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'campagne', 'code', 'nom', 'type_equipe', 'actif'
            )
        }),
        ('Zone de couverture', {
            'fields': (
                'pole', 'region', 'district', 'centre',
                'zone_principale_label'
            )
        }),
        ('Composition de l\'équipe', {
            'fields': (
                'responsable', 'membres'
            )
        }),
        ('Contact et logistique', {
            'fields': (
                'telephone_contact', 'moyen_deplacement'
            )
        }),
        ('Statistiques opérationnelles', {
            'fields': (
                'enfants_vaccines', 'doses_administrees',
                'incidents_signales', 'performance_display_field',
                'taux_incidents_field'
            )
        }),
        ('Métadonnées', {
            'fields': (
                'date_creation', 'date_modification', 'meta'
            ),
            'classes': ('collapse',)
        })
    )

    filter_horizontal = ['membres']
    raw_id_fields = ['responsable', 'pole', 'region', 'district', 'centre']

    # ✅ Bulk actions Django
    actions = ['activer_equipes', 'desactiver_equipes']

    def campagne_link(self, obj):
        """Lien vers la campagne."""
        url = reverse('admin:pev_pevcampaignteam_change', args=[obj.campagne.pk])
        return format_html('<a href="{}">{}</a>', url, obj.campagne.code)

    campagne_link.short_description = 'Campagne'

    def responsable_link(self, obj):
        """Lien vers le responsable."""
        if obj.responsable:
            url = reverse('admin:inhp_utilisateur_change', args=[obj.responsable.pk])
            return format_html(
                '<a href="{}">{} {}</a>',
                url, obj.responsable.first_name, obj.responsable.last_name
            )
        return '-'

    responsable_link.short_description = 'Responsable'

    def zone_display(self, obj):
        """Affichage concis de la zone."""
        if obj.centre:
            return f"Centre: {obj.centre.nom[:20]}..."
        if obj.district:
            return f"District: {obj.district.nom[:20]}..."
        if obj.region:
            return f"Région: {obj.region.name[:20]}..."
        if obj.pole:
            return f"Pôle: {obj.pole.name[:20]}..."
        return '-'

    zone_display.short_description = 'Zone'

    def performance_display(self, obj):
        """Indicateur de performance visuel."""
        if obj.doses_administrees > 0:
            performance = (obj.enfants_vaccines / obj.doses_administrees) * 100
            color = 'green' if performance > 80 else 'orange' if performance > 60 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                color, performance
            )
        return '-'

    performance_display.short_description = 'Performance'

    def performance_display_field(self, obj):
        """Champ calculé pour la performance."""
        if obj.doses_administrees > 0:
            performance = (obj.enfants_vaccines / obj.doses_administrees) * 100
            return f"{performance:.1f}%"
        return "-"

    performance_display_field.short_description = "Taux de performance"

    def taux_incidents_field(self, obj):
        """Champ calculé pour le taux d'incidents."""
        if obj.doses_administrees > 0:
            taux = (obj.incidents_signales / obj.doses_administrees) * 100
            color = 'red' if taux > 5 else 'orange' if taux > 2 else 'green'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
                color, taux
            )
        return "-"

    taux_incidents_field.short_description = "Taux d'incidents"

    # ---------- Colonne Actions (ligne) ----------

    def row_actions(self, obj):
        """Boutons d'action rapides (colonne) pour l'équipe."""
        link = (
            f'<a href="{reverse("admin:pev_pevcampaignteam_stats", args=[obj.pk])}" '
            f'class="button" style="background: #FF9800; color: white; padding: 5px 10px; '
            f'text-decoration: none; border-radius: 3px; font-size: 12px;">Stats Agents</a>'
        )
        return format_html(link)

    row_actions.short_description = 'Actions'

    # ---------- Bulk actions ----------

    def activer_equipes(self, request, queryset):
        queryset.update(actif=True)
        self.message_user(request, f"{queryset.count()} équipes activées.")

    activer_equipes.short_description = "Activer les équipes sélectionnées"

    def desactiver_equipes(self, request, queryset):
        queryset.update(actif=False)
        self.message_user(request, f"{queryset.count()} équipes désactivées.")

    desactiver_equipes.short_description = "Désactiver les équipes sélectionnées"

    # ---------- URLs custom admin ----------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/stats/',
                self.admin_site.admin_view(self.stats_agents_view),
                name='pev_pevcampaignteam_stats',
            ),
        ]
        return custom_urls + urls

    def stats_agents_view(self, request, pk):
        """Vue pour afficher les statistiques des agents."""
        from django.shortcuts import render, get_object_or_404
        equipe = get_object_or_404(PEVCampaignTeam, pk=pk)
        stats_agents = equipe.stats_par_agent()

        context = {
            'title': f'Statistiques des agents - {equipe.nom}',
            'equipe': equipe,
            'stats_agents': stats_agents,
            'opts': self.model._meta,
        }

        return render(request, 'admin/vaccination/pevcampaignteam_stats.html', context)


# ==============================
#  ServiceVaccination admin
# ==============================

@admin.register(ServiceVaccination)
class ServiceVaccinationAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'nom_court', 'actif']
    list_filter = ['actif', 'type_service', 'ville', 'pays']
    search_fields = ['code', 'nom', 'nom_court', 'ville', 'pays']