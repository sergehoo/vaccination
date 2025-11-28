from datetime import date
# from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django.contrib.gis.db.models import PointField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from dateutil.relativedelta import relativedelta
# vaccination/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# from inhp.models import  Patient, CentreVaccination, Vaccination, Utilisateur



class RendezVousType(models.TextChoices):
    INFANT_PEV = "infant_pev", "Vaccination infantile (PEV)"
    INFANT_RATTRAP = "infant_rattrapage", "Rattrapage infantile"
    ADULT_ROUTINE = "adult_routine", "Vaccination adulte"
    VOYAGE = "voyage", "Vaccination voyage"
    RAPPEL = "rappel", "Rappel de vaccination"
    GROUPE = "groupe", "Vaccination de groupe"
    CAMPAGNE = "campagne", "Vaccination de campagne"
    URGENCE = "urgence", "Vaccination d'urgence"
    AUTRE = "autre", "Autre"


class RendezVousStatut(models.TextChoices):
    PLANIFIE = "planifie", "Planifié"
    CONFIRME = "confirme", "Confirmé"
    HONORE = "honore", "Honoré"
    ABSENT = "absent", "Absent (no show)"
    ANNULE = "annule", "Annulé"
    REPORTE = "reporte", "Reporté"


class RendezVousCanal(models.TextChoices):
    FRONT_OFFICE = "front", "Accueil / Centre"
    TELEPHONE = "tel", "Téléphone"
    WEB = "web", "Portail web"
    SMS = "sms", "SMS"
    MOBILE_APP = "app", "Application mobile"
    PARTENAIRE = "partenaire", "Partenaire santé"
    AUTRE = "autre", "Autre"


class PEVTrancheAge(models.TextChoices):
    NAISSANCE = "naissance", "Naissance"
    S6 = "6_sem", "6 semaines"
    S10 = "10_sem", "10 semaines"
    S14 = "14_sem", "14 semaines"
    M9 = "9_mois", "9 mois"
    M15 = "15_mois", "15 mois"
    M18 = "18_mois", "18 mois"
    M24 = "24_mois", "24 mois"
    AUTRE = "autre", "Autre"


class PEVAntigene(models.TextChoices):
    BCG = "bcg", "BCG"
    PENTA = "penta", "Pentavalent"
    VPO = "vpo", "VPO"
    VPI = "vpi", "VPI"
    RRO = "rro", "Rougeole – Rubéole – Oreillons"
    ROUGEOLE = "rougeole", "Rougeole / RR"
    FJ = "fj", "Fièvre jaune"
    PNEUMO = "pneumo", "Pneumocoque"
    ROTAVIRUS = "rota", "Rotavirus"
    VARICELLE = "varicelle", "Varicelle"
    HEPB = "hepb", "Hépatite B"
    AUTRE = "autre", "Autre"


class PrioriteRendezVous(models.TextChoices):
    NORMALE = "normale", "Normale"
    ELEVEE = "elevee", "Élevée"
    URGENT = "urgent", "Urgent"


class RendezVousVaccination(models.Model):
    """
    RDV de vaccination multi-service (INHP, PEV, ...),
    avec support spécifique pour la vaccination infantile PEV.
    """

    # ---- Contexte multi-service ----
    service = models.ForeignKey(
        'ServiceVaccination',
        on_delete=models.PROTECT,
        related_name="rendez_vous",
        help_text="Service gestionnaire du RDV (INHP, PEV, ...)",
    )

    patient = models.ForeignKey(
        'Patient',
        on_delete=models.PROTECT,
        related_name="rendez_vous_vaccination",
    )

    centre = models.ForeignKey(
        'CentreVaccination',
        on_delete=models.PROTECT,
        related_name="rendez_vous_vaccination",
        help_text="Centre où le patient doit se présenter",
    )

    # ---- Liens avec la vaccination réelle ----
    vaccination_cible = models.ForeignKey(
        'Vaccination',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rendez_vous_associes",
        help_text="Vaccination associée lorsque le RDV est honoré (optionnel).",
    )

    # ---- Infos RDV ----
    type_rdv = models.CharField(
        max_length=30,
        choices=RendezVousType.choices,
        default=RendezVousType.ADULT_ROUTINE,
    )

    statut = models.CharField(
        max_length=20,
        choices=RendezVousStatut.choices,
        default=RendezVousStatut.PLANIFIE,
    )

    canal_prise = models.CharField(
        max_length=10,
        choices=RendezVousCanal.choices,
        default=RendezVousCanal.FRONT_OFFICE,
    )

    date_heure = models.DateTimeField(
        help_text="Date et heure du rendez-vous prévu.",
    )

    date_heure_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de fin calculée automatiquement.",
    )

    duree_minutes = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(180)],
        help_text="Durée prévue du RDV en minutes."
    )

    priorite = models.CharField(
        max_length=10,
        choices=PrioriteRendezVous.choices,
        default=PrioriteRendezVous.NORMALE,
        help_text="Niveau de priorité du rendez-vous"
    )

    motif = models.CharField(
        max_length=255,
        blank=True,
        help_text="Motif libre ou complément (ex: voyage, rattrapage...)."
    )

    commentaire = models.TextField(blank=True)

    # ---- Champs spécifiques PEV (vaccination infantile) ----
    est_pev = models.BooleanField(
        default=False,
        help_text="Coché si le RDV appartient au programme PEV (vaccination infantile).",
    )

    pev_tranche_age = models.CharField(
        max_length=20,
        choices=PEVTrancheAge.choices,
        blank=True,
        help_text="Tranche d'âge PEV (naissance, 6 semaines, 9 mois...)."
    )

    pev_antigene = models.CharField(
        max_length=20,
        choices=PEVAntigene.choices,
        blank=True,
        help_text="Antigène / vaccin principal du calendrier PEV."
    )

    pev_numero_dose = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Numéro de dose pour le schéma PEV (ex: Penta 1, Penta 2, ...)."
    )

    # ---- Notifications et rappels ----
    notifications_envoyees = models.JSONField(
        default=dict,
        blank=True,
        help_text="Historique des notifications envoyées"
    )

    prochaine_notification = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Prochaine notification programmée"
    )

    consentement_notifications = models.BooleanField(
        default=True,
        help_text="Le patient accepte de recevoir des notifications"
    )

    # ---- Gestion des conflits et chevauchements ----
    chevauchement_verifie = models.BooleanField(default=False)
    conflit_avec = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conflit_pour',
        help_text="RDV en conflit avec celui-ci"
    )

    # ---- Gestion & traçabilité ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        'Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rendez_vous_crees",
    )

    updated_by = models.ForeignKey(
        'Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rendez_vous_modifies",
    )

    personnel_affecte = models.ForeignKey(
        'Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rendez_vous_affectes",
        help_text="Personnel de santé affecté à ce RDV"
    )

    motif_annulation = models.TextField(
        blank=True,
        help_text="Raison en cas d'annulation ou d'absence."
    )

    date_statut = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date du dernier changement de statut"
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données additionnelles (ex: source, référence externe...)."
    )

    class Meta:
        verbose_name = "Rendez-vous de vaccination"
        verbose_name_plural = "Rendez-vous de vaccination"
        ordering = ["-date_heure"]
        indexes = [
            models.Index(fields=["service", "centre", "date_heure"]),
            models.Index(fields=["service", "patient", "date_heure"]),
            models.Index(fields=["statut", "date_heure"]),
            models.Index(fields=["est_pev", "pev_tranche_age"]),
            models.Index(fields=["priorite", "date_heure"]),
            models.Index(fields=["prochaine_notification"]),
            models.Index(fields=["personnel_affecte", "date_heure"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(est_pev=True, pev_antigene=""),
                name="pev_antigene_obligatoire_si_est_pev",
                violation_error_message="L'antigène PEV est obligatoire quand est_pev est vrai.",
            ),
            models.CheckConstraint(
                check=models.Q(date_heure_fin__gt=models.F("date_heure")),
                name="date_fin",
            ),
        ]

    def __str__(self):
        return f"RDV {self.patient} le {self.date_heure} au {self.centre}"

    def clean(self):
        """Validation avancée du modèle"""
        super().clean()

        errors = {}

        # Validation des dates
        if self.date_heure and self.date_heure < timezone.now():
            errors['date_heure'] = _("La date du rendez-vous ne peut pas être dans le passé.")

        # Validation PEV
        if self.est_pev and not self.pev_antigene:
            errors['pev_antigene'] = _("L'antigène PEV est obligatoire pour les rendez-vous PEV.")

        # Validation de la durée
        if self.duree_minutes < 5:
            errors['duree_minutes'] = _("La durée minimum est de 5 minutes.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Surcharge de save pour calculs automatiques"""
        # Calcul automatique de la date de fin
        if self.date_heure and self.duree_minutes:
            self.date_heure_fin = self.date_heure + timezone.timedelta(minutes=self.duree_minutes)

        # Mise à jour de la date de statut
        if self.pk:
            old_instance = RendezVousVaccination.objects.get(pk=self.pk)
            if old_instance.statut != self.statut:
                self.date_statut = timezone.now()
        else:
            self.date_statut = timezone.now()

        super().save(*args, **kwargs)

    # ---- Properties métier ----
    @property
    def is_future(self):
        return self.date_heure >= timezone.now()

    @property
    def is_today(self):
        today = timezone.now().date()
        return self.date_heure.date() == today

    @property
    def is_past(self):
        return self.date_heure < timezone.now()

    @property
    def is_urgent(self):
        return self.priorite == PrioriteRendezVous.URGENT

    @property
    def time_until_appointment(self):
        """Temps restant avant le RDV"""
        if self.is_future:
            return self.date_heure - timezone.now()
        return None

    @property
    def needs_confirmation(self):
        """Le RDV nécessite-t-il une confirmation ?"""
        return (self.statut == RendezVousStatut.PLANIFIE and
                self.time_until_appointment and
                self.time_until_appointment.days <= 1)

    @property
    def can_be_modified(self):
        """Le RDV peut-il être modifié ?"""
        return self.statut in [RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME] and self.is_future

    @property
    def can_be_cancelled(self):
        """Le RDV peut-il être annulé ?"""
        return self.statut in [RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME]

    # ---- Méthodes métier ----
    def marquer_confirme(self, user=None):
        """Marquer le RDV comme confirmé"""
        self.statut = RendezVousStatut.CONFIRME
        if user:
            self.updated_by = user
        self.save(update_fields=["statut", "updated_by", "updated_at", "date_statut"])

    def marquer_honore(self, vaccination=None, user=None):
        """Marquer le RDV comme honoré"""
        self.statut = RendezVousStatut.HONORE
        if vaccination:
            self.vaccination_cible = vaccination
        if user:
            self.updated_by = user
        self.save(update_fields=["statut", "vaccination_cible", "updated_by", "updated_at", "date_statut"])

    def marquer_absent(self, motif=None, user=None):
        """Marquer le RDV comme absent"""
        self.statut = RendezVousStatut.ABSENT
        if motif:
            self.motif_annulation = motif
        if user:
            self.updated_by = user
        self.save(update_fields=["statut", "motif_annulation", "updated_by", "updated_at", "date_statut"])

    def marquer_annule(self, motif=None, user=None):
        """Annuler le RDV"""
        self.statut = RendezVousStatut.ANNULE
        if motif:
            self.motif_annulation = motif
        if user:
            self.updated_by = user
        self.save(update_fields=["statut", "motif_annulation", "updated_by", "updated_at", "date_statut"])

    def reporter(self, nouvelle_date_heure, user=None):
        """Reporter le RDV à une nouvelle date"""
        if not self.can_be_modified:
            raise ValidationError(_("Ce rendez-vous ne peut pas être reporté."))

        self.date_heure = nouvelle_date_heure
        self.statut = RendezVousStatut.REPORTE
        if user:
            self.updated_by = user
        self.save()

    def ajouter_notification(self, type_notif, date_envoi, statut="envoyee"):
        """Ajouter une notification à l'historique"""
        if 'notifications' not in self.notifications_envoyees:
            self.notifications_envoyees['notifications'] = []

        self.notifications_envoyees['notifications'].append({
            'type': type_notif,
            'date_envoi': date_envoi.isoformat(),
            'statut': statut
        })
        self.save(update_fields=['notifications_envoyees'])

    def verifier_chevauchement(self):
        """Vérifier s'il y a chevauchement avec d'autres RDV"""
        if not self.date_heure or not self.date_heure_fin:
            return None

        conflits = RendezVousVaccination.objects.filter(
            centre=self.centre,
            personnel_affecte=self.personnel_affecte,
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME],
            date_heure__lt=self.date_heure_fin,
            date_heure_fin__gt=self.date_heure
        ).exclude(pk=self.pk)

        if conflits.exists():
            self.conflit_avec = conflits.first()
            self.chevauchement_verifie = True
            self.save()
            return conflits.first()

        return None

    # ---- Méthodes de classe ----
    @classmethod
    def rdv_du_jour(cls, centre=None, service=None):
        """Récupérer les RDV du jour"""
        queryset = cls.objects.filter(
            date_heure__date=timezone.now().date(),
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME]
        )

        if centre:
            queryset = queryset.filter(centre=centre)
        if service:
            queryset = queryset.filter(service=service)

        return queryset.order_by('date_heure')

    @classmethod
    def rdv_a_venir(cls, jours=7, centre=None):
        """Récupérer les RDV à venir dans les X prochains jours"""
        date_debut = timezone.now()
        date_fin = date_debut + timezone.timedelta(days=jours)

        queryset = cls.objects.filter(
            date_heure__range=[date_debut, date_fin],
            statut__in=[RendezVousStatut.PLANIFIE, RendezVousStatut.CONFIRME]
        )

        if centre:
            queryset = queryset.filter(centre=centre)

        return queryset.order_by('date_heure')

    @classmethod
    def statistiques_centre(cls, centre, date_debut, date_fin):
        """Statistiques des RDV pour un centre sur une période"""
        rdvs = cls.objects.filter(
            centre=centre,
            date_heure__range=[date_debut, date_fin]
        )

        return {
            'total': rdvs.count(),
            'honores': rdvs.filter(statut=RendezVousStatut.HONORE).count(),
            'absents': rdvs.filter(statut=RendezVousStatut.ABSENT).count(),
            'annules': rdvs.filter(statut=RendezVousStatut.ANNULE).count(),
            'taux_honores': rdvs.filter(
                statut=RendezVousStatut.HONORE).count() / rdvs.count() * 100 if rdvs.count() > 0 else 0,
        }

    @property
    def duree_estimee(self):
        return self.duree_minutes

    @property
    def est_aujourdhui(self):
        return self.is_today

    @property
    def est_dans_24h(self):
        if not self.time_until_appointment:
            return False
        return self.time_until_appointment.total_seconds() <= 24 * 3600

    @property
    def est_passe(self):
        return self.is_past

    @property
    def peut_etre_annule(self):
        return self.can_be_cancelled

    @property
    def peut_etre_modifie(self):
        return self.can_be_modified

    @property
    def label_priorite(self):
        return self.get_priorite_display()

    @property
    def label_canal(self):
        return self.get_canal_prise_display()

    @property
    def resume_pev(self):
        if not self.est_pev:
            return ""
        parts = []
        if self.pev_tranche_age:
            parts.append(self.get_pev_tranche_age_display())
        if self.pev_antigene:
            parts.append(self.get_pev_antigene_display())
        if self.pev_numero_dose:
            parts.append(f"Dose n°{self.pev_numero_dose}")
        return " · ".join(parts)


class ServiceVaccination(models.Model):
    # Types de services disponibles
    SERVICE_TYPES = [
        ('public', 'Public'),
        ('prive', 'Privé'),
        ('associatif', 'Associatif'),
        ('mixte', 'Mixte Public-Privé'),
    ]

    # Niveaux d'accessibilité
    ACCESSIBILITY_LEVELS = [
        ('faible', 'Faible'),
        ('moyen', 'Moyen'),
        ('bon', 'Bon'),
        ('excellent', 'Excellent'),
    ]

    # Identifiants uniques
    code = models.CharField(max_length=20, unique=True)  # "INHP", "PEV"
    nom = models.CharField(max_length=150)
    nom_court = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="URL-friendly version du nom")

    # Type et catégorisation
    type_service = models.CharField(max_length=20, choices=SERVICE_TYPES, default='public')
    categorie = models.CharField(max_length=50, blank=True,
                                 help_text="Ex: Vaccination générale, Vaccination voyage, etc.")
    tags = models.JSONField(default=list, blank=True, help_text="Tags pour la recherche et filtrage")

    # Informations de contact
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    site_web = models.URLField(blank=True)

    # Localisation
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    pays = models.CharField(max_length=50, default="France")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Branding amélioré
    logo = models.ImageField(upload_to="brandings/", null=True, blank=True)
    banniere = models.ImageField(upload_to="brandings/bannieres/", null=True, blank=True,
                                 help_text="Bannière pour le header du service")
    favicon = models.ImageField(upload_to="brandings/favicons/", null=True, blank=True)

    primary_color = models.CharField(max_length=7, default="#0f766e")
    secondary_color = models.CharField(max_length=7, default="#0ea5e9")
    accent_color = models.CharField(max_length=7, default="#f97316")
    text_color = models.CharField(max_length=7, default="#1f2937")
    background_color = models.CharField(max_length=7, default="#ffffff")

    # Configuration des fonctionnalités
    enabled_features = models.JSONField(default=list, blank=True)
    feature_config = models.JSONField(default=dict, blank=True,
                                      help_text="Configuration spécifique des fonctionnalités")

    # Paramètres opérationnels
    heures_ouverture = models.JSONField(default=dict, blank=True,
                                        help_text="Heures d'ouverture au format JSON")
    capacite_quotidienne = models.PositiveIntegerField(default=100,
                                                       help_text="Nombre maximum de vaccinations par jour")
    duree_rdv_moyenne = models.PositiveIntegerField(default=15,
                                                    help_text="Durée moyenne d'un rendez-vous en minutes")

    # Accessibilité
    niveau_accessibilite = models.CharField(max_length=15, choices=ACCESSIBILITY_LEVELS, default='moyen')
    services_accessibilite = models.JSONField(default=list, blank=True,
                                              help_text="Ex: ['pmr', 'parking', 'traducteur']")

    # Métriques et statistiques
    note_moyenne = models.DecimalField(max_digits=3, decimal_places=2, default=0.0,
                                       validators=[MinValueValidator(0), MaxValueValidator(5)])
    nombre_avis = models.PositiveIntegerField(default=0)
    vaccinations_realisees = models.PositiveBigIntegerField(default=0)

    # Sécurité et conformité
    certificat_qualite = models.BooleanField(default=False)
    date_certification = models.DateField(null=True, blank=True)
    organisme_certificateur = models.CharField(max_length=100, blank=True)

    # Métadonnées
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    date_activation = models.DateTimeField(null=True, blank=True)

    # Responsable
    responsable_nom = models.CharField(max_length=100, blank=True)
    responsable_email = models.EmailField(blank=True)
    responsable_telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Service de vaccination"
        verbose_name_plural = "Services de vaccination"
        indexes = [
            models.Index(fields=['actif', 'type_service']),
            models.Index(fields=['ville', 'code_postal']),
            models.Index(fields=['note_moyenne']),
        ]
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.nom_court or self.nom)

        if self.actif and not self.date_activation:
            self.date_activation = timezone.now()

        super().save(*args, **kwargs)

    def has_feature(self, feature_key: str) -> bool:
        return feature_key in (self.enabled_features or [])

    def get_feature_config(self, feature_key: str, default=None):
        """Récupère la configuration d'une fonctionnalité spécifique"""
        return self.feature_config.get(feature_key, default)

    def get_absolute_url(self):
        return reverse('service-detail', kwargs={'slug': self.slug})

    def increment_vaccinations(self, count=1):
        """Incrémente le compteur de vaccinations réalisées"""
        self.vaccinations_realisees += count
        self.save(update_fields=['vaccinations_realisees'])

    def update_rating(self, new_note):
        """Met à jour la note moyenne du service"""
        total_notes = (self.note_moyenne * self.nombre_avis) + new_note
        self.nombre_avis += 1
        self.note_moyenne = total_notes / self.nombre_avis
        self.save(update_fields=['note_moyenne', 'nombre_avis'])

    def is_open_now(self):
        """Vérifie si le service est actuellement ouvert"""
        if not self.heures_ouverture:
            return False

        now = timezone.now()
        current_day = now.strftime('%A').lower()
        current_time = now.time()

        day_schedule = self.heures_ouverture.get(current_day, {})
        if not day_schedule.get('ouvert', False):
            return False

        ouvert = day_schedule.get('ouverture')
        ferme = day_schedule.get('fermeture')

        if ouvert and ferme:
            return ouvert <= current_time <= ferme

        return False

    def get_capacity_utilization(self, date=None):
        """Calcule le taux d'utilisation de la capacité"""
        from django.db.models import Count

        if date is None:
            date = timezone.now().date()

        appointments_count = RendezVousVaccination.objects.filter(
            service=self,
            date__date=date,
            statut='confirme'
        ).count()

        return (appointments_count / self.capacite_quotidienne) * 100 if self.capacite_quotidienne > 0 else 0

    @property
    def adresse_complete(self):
        """Retourne l'adresse complète formatée"""
        parts = [self.adresse, self.code_postal, self.ville, self.pays]
        return ", ".join(filter(None, parts))

    @property
    def is_certified(self):
        """Vérifie si la certification est valide (moins d'un an)"""
        if not self.certificat_qualite or not self.date_certification:
            return False
        return (timezone.now().date() - self.date_certification).days <= 365

    @classmethod
    def get_active_services(cls):
        return cls.objects.filter(actif=True)

    @classmethod
    def get_services_by_type(cls, service_type):
        return cls.objects.filter(actif=True, type_service=service_type)

    @classmethod
    def get_services_by_location(cls, ville=None, code_postal=None):
        queryset = cls.objects.filter(actif=True)
        if ville:
            queryset = queryset.filter(ville__icontains=ville)
        if code_postal:
            queryset = queryset.filter(code_postal__icontains=code_postal)
        return queryset


class PolesRegionaux(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return self.name if self.name else "Unnamed Pole"


class HealthRegion(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    poles = models.ForeignKey(PolesRegionaux, on_delete=models.SET_NULL, null=True, blank=True, related_name='regions')

    def __str__(self):
        return self.name


class DistrictSanitaire(models.Model):
    nom = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    region = models.ForeignKey(HealthRegion, on_delete=models.CASCADE, null=True, blank=True, related_name='districts')
    geom = PointField(null=True, blank=True)
    geojson = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.nom}'


class TypeServiceSanitaire(models.Model):
    nom = models.CharField(max_length=500, null=True, blank=True)
    acronyme = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.acronyme}"


class CentreBasedPermission(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur peut accéder aux données selon son niveau.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.access_level == 'pole' and obj.centre.district.region.poles == user.pole:
            return True
        if user.access_level == 'region' and obj.centre.district.region == user.region:
            return True
        if user.access_level == 'district' and obj.centre.district == user.district:
            return True
        if user.access_level == 'centre' and obj.centre == user.centre:
            return True

        return False


# Create your models here.
class CentreVaccination(models.Model):
    name = models.CharField(max_length=255)
    type = models.ForeignKey(TypeServiceSanitaire, on_delete=models.SET_NULL, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    district = models.ForeignKey(DistrictSanitaire, on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='centres')
    geom = PointField(null=True, blank=True)
    adresse = models.TextField(null=True, blank=True)
    service = models.ForeignKey(
        ServiceVaccination,
        on_delete=models.PROTECT,
        related_name="centres",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    AGENT_SAISIE = "agent_saisie", _("Agent de Saisie")
    SUPERVISEUR = "superviseur", _("Superviseur")
    RESPONSABLE = "responsable", _("Responsable")
    PATIENT = "patient", _("Patient")


class AccessLevel(models.TextChoices):
    CENTRE = "centre", _("Centre de Vaccination")
    DISTRICT = "district", _("District Sanitaire")
    REGION = "region", _("Région Sanitaire")
    POLE = "pole", _("Pôle Régional")
    NATIONAL = "national", _("National")


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("L'adresse e-mail est obligatoire"))
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT_SAISIE)
    # Affectation
    centre = models.ForeignKey('CentreVaccination', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='utilisateurs_centre')
    district = models.ForeignKey('DistrictSanitaire', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='utilisateurs_district')
    region = models.ForeignKey('HealthRegion', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='utilisateurs_regions')
    pole = models.ForeignKey('PolesRegionaux', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='utilisateurs_pole')

    # Niveau d'accès
    access_level = models.CharField(max_length=20, null=True, blank=True, choices=AccessLevel.choices,
                                    default=AccessLevel.CENTRE)

    # Définition des related_name pour éviter les conflits avec auth.User
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="utilisateur_groups",

    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="utilisateur_permissions",

    )
    is_active = models.BooleanField(default=True, null=True, blank=True, )
    is_staff = models.BooleanField(default=False, null=True, blank=True, )
    date_joined = models.DateTimeField(default=timezone.now)
    active_otp = models.BooleanField(default=True, null=True, blank=True, )
    ip = models.TextField(null=True, blank=True)
    ip_intrus = models.TextField(null=True, blank=True)
    code = models.TextField(null=True, blank=True)
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    service = models.ForeignKey(
        ServiceVaccination,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="utilisateurs",
        help_text="Service / programme auquel est rattaché cet utilisateur (INHP, PEV, …)."
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class PatientManager(BaseUserManager):
    def create_user(self, code_patient, password=None, **extra_fields):
        """
        - USERNAME_FIELD = code_patient
        - Si password n'est pas fourni :
            → on utilise telephone1 comme mot de passe initial
            → sinon on génère un mot de passe aléatoire
        """
        if not code_patient:
            raise ValueError("Le code patient est obligatoire")

        # On récupère éventuellement le téléphone passé dans extra_fields
        telephone = extra_fields.get("telephone1")

        user = self.model(code_patient=code_patient, **extra_fields)

        if password is None:
            if telephone:
                # Ici tu peux choisir : téléphone complet ou derniers chiffres
                password = str(telephone)
            else:
                password = self.make_random_password()

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, code_patient, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(code_patient, password, **extra_fields)


class Patient(AbstractBaseUser, PermissionsMixin):
    code_patient = models.CharField(max_length=100, unique=True, db_index=True)
    cmu_num = models.CharField(max_length=300, unique=True, db_index=True, blank=True, null=True)
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    nom = models.CharField(max_length=255, db_index=True)
    prenoms = models.CharField(max_length=255, db_index=True)
    date_naissance = models.DateField(db_index=True)
    sexe = models.CharField(max_length=10, choices=[('M', 'Masculin'), ('F', 'Féminin')])
    situation_matrimoniale = models.CharField(max_length=50, blank=True, null=True)
    nombre_enfant = models.IntegerField(default=0, blank=True, null=True)
    nationalite = models.CharField(max_length=100)
    type_piece = models.CharField(max_length=100)
    num_piece = models.CharField(max_length=100, unique=True, blank=True, null=True)
    telephone1 = models.CharField(max_length=50, blank=True, null=True)
    telephone2 = models.CharField(max_length=50, blank=True, null=True)
    commune = models.CharField(max_length=255)
    quartier = models.CharField(max_length=255)
    niveau_instruction = models.CharField(max_length=100, blank=True, null=True)
    profession = models.CharField(max_length=100, blank=True, null=True)
    consentement_parental = models.BooleanField(default=False)
    statut = models.CharField(max_length=50, choices=[('actif', 'Actif'), ('inactif', 'Inactif')], default='actif')
    centre = models.ForeignKey(CentreVaccination, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='patients')
    centre_actuel = models.ForeignKey(CentreVaccination, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='patients_actuels')
    code_otp = models.CharField(max_length=10, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)

    # 🔹 Lien vers le parent / tuteur s’il s’agit d’un mineur
    responsable = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enfants_suivis',
        help_text="Patient responsable légal (parent / tuteur) de ce patient mineur."
    )

    # 🔹 Infos complémentaires sur le parent (si pas de compte patient parent)
    nom_parent = models.CharField(max_length=255, blank=True, null=True)
    prenoms_parent = models.CharField(max_length=255, blank=True, null=True)
    telephone_parent = models.CharField(max_length=50, blank=True, null=True)
    lien_parente = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Ex: Père, Mère, Tuteur, Oncle..."
    )

    must_change_password = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True)
    groups = models.ManyToManyField(
        Group,
        related_name="patient_groups",
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="patient_permissions",
        blank=True
    )

    USERNAME_FIELD = 'code_patient'
    REQUIRED_FIELDS = ['nom', 'prenoms', 'date_naissance', 'telephone1']

    objects = PatientManager()
    service = models.ForeignKey(
        ServiceVaccination,
        on_delete=models.PROTECT,
        related_name="patients",
        null=True,
        blank=True

    )
    notify_on_pass_scan = models.BooleanField(
        default=True,
        help_text="Informer le patient à chaque fois que son carnet/pass vaccinal est scanné."
    )
    last_pass_scan_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Dernière fois où le carnet/pass a été scanné."
    )

    def is_account_locked(self):
        if self.account_locked_until and timezone.now() < self.account_locked_until:
            return True
        return False

    @property
    def age(self):
        """Retourne l'âge du patient en années (calcul précis au jour près)."""
        if not self.date_naissance:
            return None

        today = date.today()

        # Calcul standard de l'âge : année courante – année de naissance
        age = today.year - self.date_naissance.year

        # Correction si l'anniversaire n'est pas encore passé cette année
        if (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day):
            age -= 1

        return age

    @property
    def est_mineur(self):
        """True si le patient a moins de 18 ans."""
        return self.age is not None and self.age < 18

    @property
    def a_un_responsable(self):
        return self.responsable is not None

    def get_full_name(self):
        return f"{self.nom} {self.prenoms}".strip()

    def get_short_name(self):
        return self.prenoms or self.nom
    def __str__(self):
        return f"{self.nom} {self.prenoms} ({self.code_patient})"


class TypeVaccin(models.TextChoices):
    ARNm = "ARNm", _("ARN messager")
    INACTIVE = "inactif", _("Virus Inactivé")
    ATTENUE = "attenue", _("Virus Atténué")
    SOUS_UNITAIRE = "sous_unitaire", _("Sous-unitaire Protéique")
    VECTEUR_VIRAL = "vecteur_viral", _("Vecteur Viral")


class TemplateConsultation(models.Model):
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    champs = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'template_consultations'
        indexes = [
            models.Index(fields=['deleted_at'], name='idx_tpl_consult_deleted')  # ≤ 30 caractères
        ]


class Maladie(models.Model):
    nom = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)

    name = models.TextField(null=True, blank=True)
    code_maladie = models.TextField(null=True, blank=True)
    formulaire_model_id = models.TextField(null=True, blank=True)
    formulaire_name = models.TextField(null=True, blank=True)
    template_consultation = models.ForeignKey('TemplateConsultation', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'maladies'
        indexes = [models.Index(fields=['deleted_at'], name='idx_maladies_deleted_at')]

    def __str__(self):
        return self.nom


class Vaccin(models.Model):
    nom = models.CharField(max_length=255, unique=True, db_index=True)
    fabricant = models.CharField(max_length=255, blank=True, null=True)
    type_vaccin = models.CharField(max_length=50, choices=TypeVaccin.choices)
    doses_requises = models.PositiveIntegerField(default=1)
    intervalle_doses = models.PositiveIntegerField(help_text="Intervalle en jours entre les doses", blank=True,
                                                   null=True)
    maladie = models.ForeignKey(Maladie, on_delete=models.CASCADE, related_name='vaccinsmaladie')
    pays_origine = models.CharField(max_length=100, blank=True, null=True)
    statut_approbation = models.BooleanField(default=True, help_text="Le vaccin est-il approuvé ?")
    duree_immunite = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Durée de l'immunité en mois après la dernière dose"
    )

    besoin_rappel = models.BooleanField(
        default=False,
        help_text="Ce vaccin nécessite-t-il un rappel après un certain temps ?"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.fabricant})"


class LotVaccin(models.Model):
    numero_lot = models.CharField(max_length=100, db_index=True)
    vaccin = models.ForeignKey(Vaccin, on_delete=models.CASCADE, related_name='lotsvaccin')
    date_fabrication = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)
    quantite_initiale = models.PositiveIntegerField(null=True, blank=True)
    quantite_disponible = models.PositiveIntegerField(null=True, blank=True)
    centre = models.ForeignKey(CentreVaccination, on_delete=models.CASCADE, related_name='lots_vaccins')
    recu = models.BooleanField(null=True, blank=True)
    is_for_all = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lot {self.numero_lot} - {self.vaccin.nom}"


class Consultation(models.Model):
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    centre = models.ForeignKey(CentreVaccination, on_delete=models.CASCADE, null=True, blank=True)
    code_patient = models.TextField(null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True, related_name='consultations')
    consultation = models.JSONField(null=True, blank=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True, blank=True)
    maladie = models.ForeignKey(Maladie, on_delete=models.CASCADE, null=True, blank=True)


class Vaccination(models.Model):
    from pev.models import PEVCampaign, PEVCampaignTeam
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='historique_vaccinations',
                                db_index=True)
    centre = models.ForeignKey(CentreVaccination, on_delete=models.CASCADE, related_name='centrevaccinations',
                               db_index=True)
    date_vaccination = models.DateField(db_index=True)
    vaccin = models.ForeignKey(Vaccin, on_delete=models.CASCADE, related_name='vaccinstype', null=True, blank=True)
    lot = models.ForeignKey(LotVaccin, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='vaccinationslots', db_index=True)
    dose = models.IntegerField(db_index=True)
    date_rappel = models.DateField(
        blank=True, null=True,
        help_text="Date prévue du rappel si applicable"
    )
    campagne_pev = models.ForeignKey(
        PEVCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccinations",
        help_text="Campagne PEV dans le cadre de laquelle cette dose a été réalisée."
    )
    service = models.ForeignKey(
        ServiceVaccination,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vaccinations"
    )

    # 🔹 Équipe PEV qui a réalisé l’acte (si en campagne)
    equipe = models.ForeignKey(
        PEVCampaignTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccinations",
        help_text="Équipe de campagne PEV ayant effectué cette vaccination."
    )

    # 🔹 Agent vaccinateur (évalué pendant la campagne)
    vaccinateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccinations_administrees",
        help_text="Agent vaccinateur ayant réalisé l'acte."
    )
    created_by = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def calculer_date_rappel(self):
        if self.vaccin and self.vaccin.besoin_rappel and self.vaccin.duree_immunite:
            return self.date_vaccination + relativedelta(months=self.vaccin.duree_immunite)
        return None

    def __str__(self):
        return f"{self.patient.nom} {self.patient.prenoms} - {self.vaccin} ({self.date_vaccination})"


class Mapi(models.Model):
    symptome = models.TextField(null=True, blank=True)
    commentaire = models.TextField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    centre = models.ForeignKey('CentreVaccination', on_delete=models.CASCADE)
    vaccination = models.ForeignKey('Vaccination', on_delete=models.CASCADE, related_name='incident')
    utilisateur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'mapis'
        indexes = [models.Index(fields=['deleted_at'], name='idx_mapis_deleted_at')]


class Message(models.Model):
    message = models.TextField()
    type = models.TextField()
    is_active = models.BooleanField(default=True)
    utilisateur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'messages'
        indexes = [models.Index(fields=['deleted_at'], name='idx_messages_deleted_at')]


class VaccineExt(models.Model):
    pays = models.TextField(null=True, blank=True)
    ville = models.TextField(null=True, blank=True)
    numero_dose = models.BigIntegerField(null=True, blank=True)
    lot = models.TextField(null=True, blank=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    vaccin = models.ForeignKey('Vaccin', on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)
    utilisateur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE)
    code_patient = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'vaccine_exts'
        indexes = [models.Index(fields=['deleted_at'], name='idx_vaccine_exts_deleted_at')]


class Equipement(models.Model):
    type = models.TextField(null=True, blank=True)
    numero_serie = models.TextField(null=True, blank=True)
    marque = models.TextField(null=True, blank=True)
    centre = models.ForeignKey(CentreVaccination, on_delete=models.CASCADE, null=True, blank=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)


class FactureCentral(models.Model):
    numero_facture = models.TextField(null=True, blank=True)
    total = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)


class FactureDistrict(models.Model):
    numero_facture = models.TextField(null=True, blank=True)
    total = models.BigIntegerField(null=True, blank=True)
    bonus = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    district = models.ForeignKey(DistrictSanitaire, on_delete=models.CASCADE, null=True, blank=True)
    ref = models.BigIntegerField(null=True, blank=True)
    total_centre = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)


class CallCenter(models.Model):
    telephone = models.TextField(null=True, blank=True)
    disponible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)


class FactureRegion(models.Model):
    numero_facture = models.TextField(null=True, blank=True)
    total = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey('Utilisateur', on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    region = models.ForeignKey('HealthRegion', on_delete=models.CASCADE)
    total_centre = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)


class Facture(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    numero_facture = models.TextField(null=True, blank=True, db_index=True)
    nbre_vaccine = models.BigIntegerField(null=True, blank=True, db_index=True)
    prix_unitaire = models.BigIntegerField(null=True, blank=True)
    total = models.BigIntegerField(null=True, blank=True)
    bonus = models.BigIntegerField(null=True, blank=True)
    total_diabete_hyper_acc = models.BigIntegerField(null=True, blank=True)
    nbre_vaccine_acc = models.BigIntegerField(null=True, blank=True)
    centre = models.ForeignKey('CentreVaccination', on_delete=models.CASCADE, db_index=True)
    created_by = models.ForeignKey('Utilisateur', on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    ref = models.BigIntegerField(null=True, blank=True)


class FatureParametre(models.Model):
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    prix_unitaire = models.BigIntegerField()


class FicheRetro(models.Model):
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    nom = models.TextField()
    prenoms = models.TextField()
    date_naissance = models.DateTimeField()
    sexe = models.TextField()
    situation_matrimoniale = models.TextField(null=True, blank=True)
    nombre_enfant = models.BigIntegerField(null=True, blank=True)
    nationnalite = models.TextField(default='Non defini')
    type_piece = models.TextField(null=True, blank=True)
    num_piece = models.TextField(null=True, blank=True)
    telephone1 = models.TextField()
    telephone2 = models.TextField(null=True, blank=True)
    commune = models.TextField(null=True, blank=True)
    quatier = models.TextField(null=True, blank=True)
    niveau_instruction = models.TextField(null=True, blank=True)
    profession = models.TextField(null=True, blank=True)
    consentement_parental = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    positif = models.BigIntegerField(null=True, blank=True)
    positif_date = models.DateTimeField(null=True, blank=True)
    vaccin_autre = models.BigIntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pathologies = models.TextField(null=True, blank=True)
    date_debut_obs = models.DateTimeField(null=True, blank=True)
    date_fin_obs = models.DateTimeField(null=True, blank=True)
    mapi = models.BigIntegerField(null=True, blank=True)
    date_mapi = models.DateTimeField(null=True, blank=True)
    region1_id = models.BigIntegerField(null=True, blank=True)
    district1_id = models.BigIntegerField(null=True, blank=True)
    aire1 = models.TextField(null=True, blank=True)
    centre1_id = models.BigIntegerField(null=True, blank=True)
    date_vac1 = models.DateTimeField(null=True, blank=True)
    vaccin1_id = models.BigIntegerField(null=True, blank=True)
    numero_lot1 = models.TextField(null=True, blank=True)
    region2_id = models.BigIntegerField(null=True, blank=True)
    district2_id = models.BigIntegerField(null=True, blank=True)
    aire2 = models.TextField(null=True, blank=True)
    centre2_id = models.BigIntegerField(null=True, blank=True)
    date_vac2 = models.DateTimeField(null=True, blank=True)
    vaccin2_id = models.BigIntegerField(null=True, blank=True)
    numero_lot2 = models.TextField(null=True, blank=True)
    region3_id = models.BigIntegerField(null=True, blank=True)
    district3_id = models.BigIntegerField(null=True, blank=True)
    aire3 = models.TextField(null=True, blank=True)
    centre3_id = models.BigIntegerField(null=True, blank=True)
    date_vac3 = models.DateTimeField(null=True, blank=True)
    vaccin3_id = models.BigIntegerField(null=True, blank=True)
    numero_lot3 = models.TextField(null=True, blank=True)
    region4_id = models.BigIntegerField(null=True, blank=True)
    district4_id = models.BigIntegerField(null=True, blank=True)
    aire4 = models.TextField(null=True, blank=True)
    centre4_id = models.BigIntegerField(null=True, blank=True)
    date_vac4 = models.DateTimeField(null=True, blank=True)
    vaccin4_id = models.BigIntegerField(null=True, blank=True)
    numero_lot4 = models.TextField(null=True, blank=True)
    utilisateur = models.ForeignKey('Utilisateur', on_delete=models.SET_NULL, null=True, blank=True)
    is_valider = models.BigIntegerField(default=0)
    date = models.DateTimeField(null=True, blank=True)
    numero_civ = models.TextField(null=True, blank=True)
    numero_unique = models.TextField(null=True, blank=True)


class VaccinationPassEvent(models.Model):
    """Trace chaque scan / utilisation du carnet ou pass vaccinal du patient."""

    class EventType(models.TextChoices):
        SCAN = "SCAN", "Scan du QR Code"
        EXPORT_PDF = "EXPORT_PDF", "Export du carnet en PDF"
        CONSULTATION = "CONSULTATION", "Consultation du carnet"
        AUTRE = "AUTRE", "Autre"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="pass_events",
        db_index=True,
    )

    type_evenement = models.CharField(
        max_length=30,
        choices=EventType.choices,
        default=EventType.SCAN,
    )

    service = models.ForeignKey(
        ServiceVaccination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pass_events",
    )

    centre = models.ForeignKey(
        CentreVaccination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pass_events",
    )

    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pass_events",
        help_text="Agent qui a scanné le carnet/pass, si connu.",
    )

    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Source technique : portail_web, appli_mobile, api_integration..."
    )

    adresse_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP du poste qui a scanné, si disponible."
    )

    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User-Agent HTTP, si disponible."
    )

    commentaire = models.TextField(
        blank=True,
        help_text="Informations complémentaires sur l’utilisation."
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données techniques additionnelles (id requête, trace, etc.)."
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Événement carnet/pass vaccinal"
        verbose_name_plural = "Événements carnet/pass vaccinal"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["centre", "created_at"]),
            models.Index(fields=["type_evenement", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_type_evenement_display()} - {self.patient} @ {self.created_at:%d/%m/%Y %H:%M}"
