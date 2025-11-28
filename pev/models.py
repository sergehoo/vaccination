from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.apps import apps
 # on le créera après

from inhp.models import Utilisateur


class PEVCampaignStatus(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    PLANIFIEE = "planifiee", "Planifiée"
    VALIDEE = "validee", "Validée"
    EN_COURS = "en_cours", "En cours"
    SUSPENDUE = "suspendue", "Suspendue"
    CLOTUREE = "cloturee", "Clôturée"
    ARCHIVEE = "archivee", "Archivée"


class PEVCampaignType(models.TextChoices):
    ROUTINE = "routine", "Routine renforcée"
    SUIVI = "suivi", "Campagne de suivi"
    RATTRAPAGE = "rattrapage", "Rattrapage"
    URGENCE = "urgence", "Riposte / Urgence"
    INTRODUCTOIRE = "intro", "Introduction nouveau vaccin"
    MASSIVE = "massive", "Campagne massive"
    PORTE_A_PORTE = "pap", "Porte à porte"
    AUTRE = "autre", "Autre"


class PEVCampaignFrequency(models.TextChoices):
    PONCTUELLE = "ponctuelle", "Ponctuelle"
    MENSUELLE = "mensuelle", "Mensuelle"
    TRIMESTRIELLE = "trimestrielle", "Trimestrielle"
    SEMESTRIELLE = "semestrielle", "Semestrielle"
    ANNUELLE = "annuelle", "Annuelle"

class PEVCampaignTeamType(models.TextChoices):
    FIXE = "fixe", "Équipe fixe"
    MOBILE = "mobile", "Équipe mobile"
    MIXTE = "mixte", "Équipe mixte"

class PEVCampaignRemunerationMode(models.TextChoices):
    A_L_ACTE = "a_l_acte", "À l’acte (par vaccination)"
    FORFAIT  = "forfait", "Forfait / autre"
    AUCUNE   = "aucune", "Non défini / hors système"
class PEVCampaign(models.Model):
    """
    Campagne PEV couvrant un territoire donné
    (pôle / région / district / centres spécifiques).
    """

    service = models.ForeignKey(
        "inhp.ServiceVaccination",
        on_delete=models.PROTECT,
        related_name="campagnes_pev",
        help_text="Normalement le service PEV, mais on garde générique.",
    null = True, blank = True,
    )

    code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Code campagne (ex: PEV-COVID-2025-01)."
    )
    nom = models.CharField(max_length=200)
    nom_court = models.CharField(max_length=100, blank=True, help_text="Nom abrégé pour les rapports")

    type_campagne = models.CharField(
        max_length=20,
        choices=PEVCampaignType.choices,
        default=PEVCampaignType.ROUTINE,

    )

    frequence = models.CharField(
        max_length=15,
        choices=PEVCampaignFrequency.choices,
        default=PEVCampaignFrequency.PONCTUELLE,
        help_text="Fréquence de la campagne"
    )

    description = models.TextField(blank=True)
    objectifs = models.TextField(blank=True, help_text="Objectifs spécifiques de la campagne")

    # Période
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_debut_reelle = models.DateField(
        null=True, blank=True, help_text="Date de début effective"
    )
    date_fin_reelle = models.DateField(
        null=True, blank=True, help_text="Date de fin effective"
    )

    statut = models.CharField(
        max_length=20,
        choices=PEVCampaignStatus.choices,
        default=PEVCampaignStatus.BROUILLON,
    )

    # Cible PEV (âge / population / antigènes)
    age_min_mois = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Âge minimum en mois (ex: 0 pour naissance, 6 pour 6 semaines)."
    )
    age_max_mois = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Âge maximum en mois (si pertinent)."
    )

    population_cible = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Population cible estimée (enfants, femmes enceintes...)."
    )

    couverture_cible = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Objectif de couverture en %, ex : 95.00."
    )

    # Budget et ressources
    budget_alloue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Budget alloué à la campagne"
    )

    budget_depense = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Budget déjà dépensé"
    )
    remuneration_mode = models.CharField(
        max_length=20,
        choices=PEVCampaignRemunerationMode.choices,
        default=PEVCampaignRemunerationMode.A_L_ACTE,
        help_text="Mode de rémunération des agents de vaccination."
    )

    montant_par_vaccination = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Montant versé à l’agent pour chaque vaccination réalisée (ex : 200.00)."
    )
    # Antigènes / vaccins concernés par la campagne
    vaccins = models.ManyToManyField(
        "inhp.Vaccin",
        blank=True,
        related_name="campagnes_pev",
        help_text="Vaccins/antigènes concernés (BCG, Penta, Rougeole...)."
    )

    # Territoires couverts
    poles = models.ManyToManyField(
        "inhp.PolesRegionaux",
        blank=True,
        related_name="campagnes_pev",
    )
    regions = models.ManyToManyField(
        "inhp.HealthRegion",
        blank=True,
        related_name="campagnes_pev",
    )
    districts = models.ManyToManyField(
        "inhp.DistrictSanitaire",
        blank=True,
        related_name="campagnes_pev",
    )
    centres = models.ManyToManyField(
        "inhp.CentreVaccination",
        blank=True,
        related_name="campagnes_pev",
    )

    # Indicateurs de performance
    # nombre_enfants_vaccines = models.PositiveIntegerField(
    #     default=0,
    #     help_text="Nombre total d'enfants vaccinés"
    # )
    #
    # doses_administrees = models.PositiveIntegerField(
    #     default=0,
    #     help_text="Nombre total de doses administrées"
    # )
    #
    # taux_couverture_reel = models.DecimalField(
    #     max_digits=5,
    #     decimal_places=2,
    #     null=True,
    #     blank=True,
    #     validators=[MinValueValidator(0), MaxValueValidator(100)],
    #     help_text="Couverture vaccinale réelle calculée"
    # )

    # Gestion des équipes
    # equipes_mobiles = models.PositiveIntegerField(
    #     default=0,
    #     help_text="Nombre d'équipes mobiles déployées"
    # )
    #
    # personnel_implique = models.PositiveIntegerField(
    #     default=0,
    #     help_text="Nombre total de personnels impliqués"
    # )

    # Sécurité et qualité
    # incidents_signales = models.PositiveIntegerField(
    #     default=0,
    #     help_text="Nombre d'incidents signalés pendant la campagne"
    # )
    #
    # taux_effets_secondaires = models.DecimalField(
    #     max_digits=5,
    #     decimal_places=2,
    #     null=True,
    #     blank=True,
    #     help_text="Pourcentage d'effets secondaires signalés"
    # )

    # Logistique
    besoin_logistique = models.JSONField(
        default=dict,
        blank=True,
        help_text="Besoins en matériel et logistique"
    )

    statut_approvisionnement = models.CharField(
        max_length=20,
        choices=[
            ('en_attente', 'En attente'),
            ('partiel', 'Partiel'),
            ('complet', 'Complet'),
            ('probleme', 'Problème'),
        ],
        default='en_attente',
        help_text="Statut de l'approvisionnement en vaccins"
    )

    # Communication
    plan_communication = models.TextField(blank=True,
        help_text="Stratégie de communication de la campagne"
    )

    partenaires_impliques = models.JSONField(
        default=list,
        blank=True,
        help_text="Partenaires impliqués dans la campagne"
    )

    # Meta / suivi
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True, related_name="campagnes_crees")

    responsable_campagne = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campagnes_responsables"
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Infos complémentaires (sources, réf. GAVI, OMS, etc.)."
    )

    class Meta:
        verbose_name = "Campagne PEV"
        verbose_name_plural = "Campagnes PEV"
        ordering = ["-date_debut"]
        indexes = [
            models.Index(fields=["service", "date_debut", "date_fin"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["type_campagne"]),
            models.Index(fields=["code"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(date_fin__gte=models.F("date_debut")),
                name="date_cloture"
            )
        ]

    @property
    def nombre_enfants_vaccines_calc(self):
        """
        Nombre d'enfants (0–6 ans) vaccinés dans cette campagne.
        On compte des patients distincts, avec un filtre d'âge.
        """
        Vaccination = apps.get_model("inhp", "Vaccination")

        today = timezone.now().date()

        # borne : 6 ans en arrière
        try:
            borne_basse = today.replace(year=today.year - 6)
        except ValueError:
            # gestion du 29 février : fallback approximatif
            borne_basse = today - timedelta(days=6 * 365)

        return (
                Vaccination.objects
                .filter(
                    campagne_pev=self,
                    deleted_at__isnull=True,  # si tu as ce champ
                    patient__date_naissance__gte=borne_basse,
                )
                .aggregate(nb=Count("patient_id", distinct=True))
                ["nb"] or 0
        )

    @property
    def nombre_patients_vaccines_calc(self):
        Vaccination = apps.get_model("inhp", "Vaccination")
        return (
                Vaccination.objects
                .filter(campagne_pev=self)
                .aggregate(nb=Count("patient", distinct=True))
                ["nb"] or 0
        )

    @property
    def doses_administrees_calc(self):
        Vaccination = apps.get_model("inhp", "Vaccination")
        return (
                Vaccination.objects
                .filter(campagne_pev=self, deleted_at__isnull=True)
                .aggregate(nb=Count("id"))
                ["nb"] or 0
        )

    @property
    def incidents_signales_calc(self):
        Vaccination = apps.get_model("inhp", "Vaccination")
        # adapte le Q() à ton modèle (champ AEFI / incident / effet secondaire…)
        return (
                Vaccination.objects
                .filter(campagne_pev=self, deleted_at__isnull=True)
                .aggregate(nb=Count("id", filter=Q(incident=True)))
                ["nb"] or 0
        )

    @property
    def taux_couverture_reel(self):
        if self.population_cible:
            # nombre_enfants_vaccines_calc = int
            return round(
                (self.nombre_enfants_vaccines_calc / float(self.population_cible)) * 100.0,
                2,
            )
        return None

    @property
    def taux_effets_secondaires(self):
        if self.nombre_enfants_vaccines_calc:
            return round(
                (self.incidents_signales_calc / self.nombre_enfants_vaccines_calc) * 100, 2
            )
        return None
    def montant_unitaire(self) -> Decimal:
        """
        Montant unitaire par vaccination pour cette campagne.
        Permet de mettre un fallback global si tu veux (settings).
        """
        if self.remuneration_par_vaccination is not None:
            return self.remuneration_par_vaccination
        return Decimal(getattr(settings, "PEV_REMUNERATION_UNITAIRE_DEFAULT", "0"))

    def remuneration_pour_agent(self, agent) -> Decimal:
        """
        Calcule la rémunération totale pour un agent (vaccinateur) sur cette campagne.
        """
        from inhp.models import Vaccination  # adapter chemin si besoin

        qs = Vaccination.objects.filter(
            campagne_pev=self,
            vaccinateur=agent,
            deleted_at__isnull=True,
        )
        nb_vaccinations = qs.count()
        return self.montant_unitaire() * Decimal(nb_vaccinations)

    def stats_agents(self):
        """
        Retourne une liste de stats par agent pour la campagne :
        - nb_vaccinations
        - nb_enfants
        - montant
        """
        from inhp.models import Vaccination  # adapter

        qs = (
            Vaccination.objects.filter(
                campagne_pev=self,
                deleted_at__isnull=True,
                vaccinateur__isnull=False,
            )
            .values("vaccinateur_id",
                    "vaccinateur__first_name",
                    "vaccinateur__last_name")
            .annotate(
                nb_vaccinations=Count("id"),
                nb_enfants=Count("patient_id", distinct=True),
            )
        )

        montant_unit = self.montant_unitaire()
        results = []
        for row in qs:
            row["montant"] = montant_unit * Decimal(row["nb_vaccinations"])
            results.append(row)
        return results

    # --- ta méthode actives_pour_centre proposée précédemment ---
    @classmethod
    def actives_pour_centre(cls, centre, date=None):
        from django.db.models import Q
        if not date:
            date = timezone.now().date()

        district = getattr(centre, "district", None)
        region = getattr(district, "region", None) if district else None
        pole = getattr(region, "poles", None) if region else None

        q_zone = Q()
        if centre:
            q_zone |= Q(centres=centre)
        if district:
            q_zone |= Q(districts=district)
        if region:
            q_zone |= Q(regions=region)
        if pole:
            q_zone |= Q(poles=pole)

        return (
            cls.objects.filter(
                actif=True,
                date_debut__lte=date,
                date_fin__gte=date,
                statut__in=[PEVCampaignStatus.PLANIFIEE, PEVCampaignStatus.EN_COURS],
            )
            .filter(q_zone)
            .distinct()
        )
    @classmethod
    def generate_next_code(cls, service=None, type_campagne=None):
        """
        Génère un code du type : PEV-ROUTINE-2025-001
        Adapter au besoin (ajout code service, etc.).
        """
        year = timezone.now().year
        type_part = (type_campagne or "GEN").upper()
        prefix = f"PEV-{type_part}-{year}-"

        last = (
            cls.objects
            .filter(code__startswith=prefix)
            .order_by('-code')
            .first()
        )
        if last:
            try:
                last_num = int(last.code.split('-')[-1])
            except ValueError:
                last_num = 0
        else:
            last_num = 0

        return f"{prefix}{last_num + 1:03d}"


    def clean(self):
        """Validation des données de la campagne"""
        super().clean()

        errors = {}

        # Validation des dates
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                errors['date_fin'] = _("La date de fin doit être postérieure à la date de début.")

        # Validation de l'âge
        if self.age_min_mois and self.age_max_mois:
            if self.age_max_mois < self.age_min_mois:
                errors['age_max_mois'] = _("L'âge maximum doit être supérieur à l'âge minimum.")

        # Validation de la couverture
        if self.couverture_cible and (self.couverture_cible < 0 or self.couverture_cible > 100):
            errors['couverture_cible'] = _("La couverture cible doit être entre 0 et 100%.")

            # Validation rémunération
        if self.remuneration_mode == PEVCampaignRemunerationMode.A_L_ACTE:
            if not self.montant_par_vaccination:
                errors["montant_par_vaccination"] = _(
                    "Veuillez renseigner le montant par vaccination pour la rémunération à l’acte."
                )
            elif self.montant_par_vaccination <= 0:
                errors["montant_par_vaccination"] = _(
                    "Le montant par vaccination doit être strictement positif."
                )


        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Surcharge de save pour calculs automatiques"""
        # Calcul automatique de la couverture réelle
        if self.population_cible and self.nombre_enfants_vaccines > 0:
            self.taux_couverture_reel = (
                    self.nombre_enfants_vaccines / self.population_cible * 100
            )

        # Calcul du taux d'effets secondaires
        if self.nombre_enfants_vaccines > 0 and self.incidents_signales > 0:
            self.taux_effets_secondaires = (self.incidents_signales / self.nombre_enfants_vaccines * 100)

        # Mise à jour automatique du statut basé sur les dates
        if self.statut not in [PEVCampaignStatus.CLOTUREE, PEVCampaignStatus.ARCHIVEE]:
            today = timezone.now().date()
            if today < self.date_debut:
                self.statut = PEVCampaignStatus.PLANIFIEE
            elif self.date_debut <= today <= self.date_fin:
                self.statut = PEVCampaignStatus.EN_COURS
            elif today > self.date_fin:
                self.statut = PEVCampaignStatus.CLOTUREE

        super().save(*args, **kwargs)

    # ---- Properties métier ----
    @property
    def est_en_cours(self):
        today = timezone.now().date()
        return (
                self.statut == PEVCampaignStatus.EN_COURS
                and self.date_debut <= today <= self.date_fin
        )

    @property
    def jours_restants(self):
        """Nombre de jours restants dans la campagne"""
        if self.est_en_cours:
            return (self.date_fin - timezone.now().date()).days
        return 0

    @property
    def progression_temps(self):
        """Progression temporelle de la campagne en pourcentage"""
        if self.date_debut and self.date_fin:
            duree_totale = (self.date_fin - self.date_debut).days
            if duree_totale > 0:
                jours_ecoules = (timezone.now().date() - self.date_debut).days
                return min(100, max(0, (jours_ecoules / duree_totale) * 100))
        return 0

    @property
    def progression_couverture(self):
        """Progression vers l'objectif de couverture"""
        tc = self.taux_couverture_reel
        if self.couverture_cible and tc is not None:
            return min(
                100.0,
                (float(tc) / float(self.couverture_cible)) * 100.0,
            )
        return 0

    @property
    def budget_utilise(self):
        """Pourcentage du budget utilisé"""
        if self.budget_alloue and self.budget_depense:
            return (self.budget_depense / self.budget_alloue) * 100
        return 0

    @property
    def efficacite_campagne(self):
        """Score d'efficacité de la campagne"""
        score = 0.0

        tc = self.taux_couverture_reel  # float ou None
        cc = float(self.couverture_cible) if self.couverture_cible else None
        pt = float(self.progression_temps) if self.progression_temps else 0.0
        pc = float(self.progression_couverture)

        if tc is not None and cc:
            score += min(100.0, (float(tc) / cc) * 50.0)

        if pt > 0:
            score += min(50.0, (pc / pt) * 50.0)

        return round(score, 2)

    @property
    def couvre_centre(self, centre: "inhp.CentreVaccination") -> bool:
        """
        Vérifie si un centre est inclus dans la campagne,
        directement ou via son district/région/pôle.
        """
        if self.centres.filter(pk=centre.pk).exists():
            return True

        district = getattr(centre, "district", None)
        region = getattr(district, "region", None) if district else None
        pole = getattr(region, "poles", None) if region else None

        if district and self.districts.filter(pk=district.pk).exists():
            return True

        if region and self.regions.filter(pk=region.pk).exists():
            return True

        if pole and self.poles.filter(pk=pole.pk).exists():
            return True

        return False
    def centres_impliques(self):
        """Retourne tous les centres impliqués dans la campagne"""
        from django.db.models import Q
        from inhp.models import CentreVaccination
        centres_directs = self.centres.all()

        # Centres via districts
        centres_via_districts = CentreVaccination.objects.filter(
            district__in=self.districts.all()
        )

        # Centres via régions
        centres_via_regions = CentreVaccination.objects.filter(
            district__region__in=self.regions.all()
        )

        # Centres via pôles
        centres_via_poles = CentreVaccination.objects.filter(
            district__region__poles__in=self.poles.all()
        )

        # Union de tous les centres
        tous_centres = (
                centres_directs |
                centres_via_districts |
                centres_via_regions |
                centres_via_poles
        ).distinct()

        return tous_centres

    # ---- Méthodes de gestion de campagne ----
    def demarrer_campagne(self):
        """Démarrer officiellement la campagne"""
        if self.statut == PEVCampaignStatus.PLANIFIEE:
            self.statut = PEVCampaignStatus.EN_COURS
            self.date_debut_reelle = timezone.now().date()
            self.save()
            return True
        return False

    def clore_campagne(self):
        """Clôturer la campagne"""
        if self.statut == PEVCampaignStatus.EN_COURS:
            self.statut = PEVCampaignStatus.CLOTUREE
            self.date_fin_reelle = timezone.now().date()
            self.save()
            return True
        return False

    def suspendre_campagne(self, motif=None):
        """Suspendre temporairement la campagne"""
        if self.statut == PEVCampaignStatus.EN_COURS:
            self.statut = PEVCampaignStatus.SUSPENDUE
            if motif:
                self.meta['suspension_motif'] = motif
                self.meta['suspension_date'] = timezone.now().isoformat()
            self.save()
            return True
        return False

    def reprendre_campagne(self):
        """Reprendre une campagne suspendue"""
        if self.statut == PEVCampaignStatus.SUSPENDUE:
            self.statut = PEVCampaignStatus.EN_COURS
            self.meta['reprise_date'] = timezone.now().isoformat()
            self.save()
            return True
        return False

    def ajouter_rapport_jour(self, date, enfants_vaccines, doses, incidents=0):
        """Ajouter un rapport journalier"""
        if 'rapports_jour' not in self.meta:
            self.meta['rapports_jour'] = []

        self.meta['rapports_jour'].append({
            'date': date.isoformat(),
            'enfants_vaccines': enfants_vaccines,
            'doses_administrees': doses,
            'incidents': incidents
        })

        # Mettre à jour les totaux
        self.nombre_enfants_vaccines += enfants_vaccines
        self.doses_administrees += doses
        self.incidents_signales += incidents

        self.save()

    # ---- Méthodes de classe ----
    @classmethod
    def campagnes_actives(cls):
        """Retourne les campagnes actives (en cours)"""
        return cls.objects.filter(
            statut=PEVCampaignStatus.EN_COURS,
            actif=True
        )

    @classmethod
    def campagnes_a_venir(cls, jours=30):
        """Retourne les campagnes à venir dans les X prochains jours"""
        date_limite = timezone.now().date() + timezone.timedelta(days=jours)
        return cls.objects.filter(
            date_debut__lte=date_limite,
            statut=PEVCampaignStatus.PLANIFIEE,
            actif=True
        )

    @classmethod
    def statistiques_globales(cls, annee=None):
        """Statistiques globales des campagnes"""
        queryset = cls.objects.filter(actif=True)
        if annee:
            queryset = queryset.filter(date_debut__year=annee)

        total_campagnes = queryset.count()
        campagnes_terminees = queryset.filter(statut=PEVCampaignStatus.CLOTUREE).count()

        return {
            'total_campagnes': total_campagnes,
            'campagnes_terminees': campagnes_terminees,
            'campagnes_en_cours': queryset.filter(statut=PEVCampaignStatus.EN_COURS).count(),
            'enfants_vaccines_total': sum(c.nombre_enfants_vaccines for c in queryset),
            'doses_administrees_total': sum(c.doses_administrees for c in queryset),
            'taux_reussite_moyen': sum(c.efficacite_campagne for c in queryset.filter(
                statut=PEVCampaignStatus.CLOTUREE)) / campagnes_terminees if campagnes_terminees > 0 else 0,
        }

    def stats_par_agent(self):
        """
        Retourne les stats par agent pour cette campagne :
        - doses_administrees
        - enfants_vaccines
        - remuneration (si montant_par_vaccination renseigné)
        """
        Vaccination = apps.get_model("inhp", "Vaccination")

        qs = (
            Vaccination.objects
            .filter(
                campagne_pev=self,
                deleted_at__isnull=True,
                vaccinateur__isnull=False,
            )
            .values(
                "vaccinateur_id",
                "vaccinateur__first_name",
                "vaccinateur__last_name",
            )
            .annotate(
                doses_administrees=Count("id"),
                enfants_vaccines=Count("patient_id", distinct=True),
            )
            .order_by("-doses_administrees")
        )

        results = []
        for row in qs:
            remuneration = None
            if self.remuneration_mode == PEVCampaignRemunerationMode.A_L_ACTE and self.montant_par_vaccination:
                remuneration = row["doses_administrees"] * float(self.montant_par_vaccination)
            row["remuneration"] = remuneration
            results.append(row)

        return results

    def get_remuneration_agent(self, user):
        """
        Rémunération d’un agent donné (utilisateur) pour cette campagne.
        """
        if not user:
            return 0

        Vaccination = apps.get_model("inhp", "Vaccination")

        doses = (
            Vaccination.objects
            .filter(
                campagne_pev=self,
                deleted_at__isnull=True,
                vaccinateur=user,
            )
            .count()
        )

        if self.remuneration_mode != PEVCampaignRemunerationMode.A_L_ACTE or not self.montant_par_vaccination:
            return 0

        return doses * float(self.montant_par_vaccination)

    @transaction.atomic
    def create_team(
            self,
            *,
            code: str,
            nom: str,
            type_equipe: str = PEVCampaignTeamType.FIXE,
            poles=None,
            regions=None,
            districts=None,
            centres=None,
            responsable=None,
            membres=None,  # iterable d'utilisateurs
            telephone_contact: str = "",
            moyen_deplacement: str = "",
            actif: bool = True,
            trigger_notifications: bool = True,
    ) -> "PEVCampaignTeam":
        """
        Crée une équipe et :
        - auto-sélectionne les membres en fonction des zones (centre/district/région/pôle),
        - ajoute aussi les membres passés en paramètre,
        - déclenche une tâche Celery pour envoyer les SMS.
        """

        # Normaliser en listes
        poles = list(poles or [])
        regions = list(regions or [])
        districts = list(districts or [])
        centres = list(centres or [])

        # 1) Vérifier unicité du code dans la campagne
        if self.equipes.filter(code=code).exists():
            raise ValidationError(
                {"code": f"Une équipe avec le code '{code}' existe déjà pour cette campagne."}
            )

        # 2) Créer l’équipe (sans encore toucher aux membres)
        team = PEVCampaignTeam.objects.create(
            campagne=self,
            code=code,
            nom=nom,
            type_equipe=type_equipe,
            # on peut éventuellement ne renseigner qu'une zone principale de rattach.
            # ici on prend le niveau le plus fin si dispo
            centre=centres[0] if centres else None,
            district=districts[0] if districts else None,
            region=regions[0] if regions else None,
            pole=poles[0] if poles else None,
            responsable=responsable,
            telephone_contact=telephone_contact,
            moyen_deplacement=moyen_deplacement,
            actif=actif,
        )

        # 3) Auto-membres en fonction des zones
        auto_member_ids = self._get_auto_members_ids(
            centres=centres,
            districts=districts,
            regions=regions,
            poles=poles,
        )

        # 4) Ajouter aussi les membres passés manuellement
        manual_member_ids = []
        if membres:
            manual_member_ids = [
                u.pk if isinstance(u, Utilisateur) else u
                for u in membres
            ]

        all_member_ids = set(auto_member_ids) | set(manual_member_ids)

        if all_member_ids:
            team.membres.add(*all_member_ids)

        # 5) Notification asynchrone
        if trigger_notifications and all_member_ids:
            from .tasks import notify_team_assignment
            notify_team_assignment.delay(
                team_id=team.pk,
                user_ids=list(all_member_ids),
            )

        return team

    def _get_auto_members_ids(self, centres=None, districts=None, regions=None, poles=None):
        """Retourne les IDs des Utilisateur auto-rattachés par zones."""
        qs = Utilisateur.objects.filter(is_active=True)

        q_filter = Q()
        if centres:
            q_filter |= Q(centre__in=centres)
        if districts:
            q_filter |= Q(district__in=districts)
        if regions:
            q_filter |= Q(region__in=regions)
        if poles:
            q_filter |= Q(pole__in=poles)

        if not q_filter.children:
            return []

        return list(
            qs.filter(q_filter).values_list("pk", flat=True).distinct()
        )

    def __str__(self):
        return f"{self.code} – {self.nom}"



class PEVCampaignTeam(models.Model):
    """
    Équipe opérationnelle dans le cadre d'une campagne PEV.
    Une campagne peut avoir plusieurs équipes, réparties sur différentes zones.
    """

    campagne = models.ForeignKey(
        PEVCampaign,
        on_delete=models.CASCADE,
        related_name="equipes",
    )

    code = models.CharField(
        max_length=30,
        help_text="Code équipe (ex : EQ-ABJ-01)."
    )
    nom = models.CharField(
        max_length=150,
        help_text="Nom ou description de l'équipe (ex : Équipe mobile Abobo Nord)."
    )

    type_equipe = models.CharField(
        max_length=10,
        choices=PEVCampaignTeamType.choices,
        default=PEVCampaignTeamType.FIXE,
    )

    # Zone principale de rattachement (une des 4, les autres restent nulles)
    pole = models.ForeignKey(
        "inhp.PolesRegionaux",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipes_pev"
    )
    region = models.ForeignKey(
        "inhp.HealthRegion",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipes_pev"
    )
    district = models.ForeignKey(
        'inhp.DistrictSanitaire',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipes_pev"
    )
    centre = models.ForeignKey(
        "inhp.CentreVaccination",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipes_pev"
    )

    # Composition de l'équipe
    responsable = models.ForeignKey(
        "inhp.Utilisateur",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="equipes_pev_responsable",
        help_text="Chef d'équipe / superviseur."
    )
    membres = models.ManyToManyField(
        "inhp.Utilisateur",
        blank=True,
        related_name="equipes_pev_membre",
        help_text="Agents vaccinateurs / relais communautaires impliqués."
    )

    # Logistique / contact
    telephone_contact = models.CharField(max_length=30, blank=True)
    moyen_deplacement = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ex : Moto, véhicule 4x4, piéton, etc."
    )

    # Statistiques opérationnelles par équipe
    enfants_vaccines = models.PositiveIntegerField(default=0)
    doses_administrees = models.PositiveIntegerField(default=0)
    incidents_signales = models.PositiveIntegerField(default=0)

    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Équipe de campagne PEV"
        verbose_name_plural = "Équipes de campagne PEV"
        ordering = ["campagne", "code"]
        unique_together = [("campagne", "code")]

    def __str__(self):
        return f"{self.campagne.code} – {self.code} – {self.nom}"

    # ---- Helpers zone ----
    @property
    def zone_principale_label(self):
        """Retourne un texte lisible pour la zone de l'équipe."""
        if self.centre:
            return f"Centre : {self.centre}"
        if self.district:
            return f"District : {self.district}"
        if self.region:
            return f"Région : {self.region}"
        if self.pole:
            return f"Pôle : {self.pole}"
        return "Zone non définie"

    # ---- Stats & MAJ ----
    def increment_stats(self, enfants=0, doses=0, incidents=0, save=True):
        """
        Incrémente les stats de l'équipe.
        À utiliser quand tu enregistres des vaccins via cette équipe.
        """
        self.enfants_vaccines += enfants
        self.doses_administrees += doses
        self.incidents_signales += incidents
        if save:
            self.save(
                update_fields=["enfants_vaccines", "doses_administrees", "incidents_signales", "date_modification"])

    def stats_par_agent(self):
        """
        Performance des agents au sein de cette équipe :
        doses + enfants distincts.
        """

        qs = (
            "inhp.Vaccination".objects
            .filter(
                campagne_pev=self.campagne,
                equipe=self,
                deleted_at__isnull=True,
                vaccinateur__isnull=False,
            )
            .values(
                "vaccinateur_id",
                "vaccinateur__first_name",
                "vaccinateur__last_name",
            )
            .annotate(
                doses_administrees=Count("id"),
                enfants_vaccines=Count("patient_id", distinct=True),
            )
            .order_by("-doses_administrees")
        )
        return list(qs)
