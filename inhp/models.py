from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from dateutil.relativedelta import relativedelta


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
        return f'{self.nom} ----> {self.region}'


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
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    district = models.ForeignKey(DistrictSanitaire, on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='centres')
    geom = PointField(null=True, blank=True)
    adresse = models.TextField()
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
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
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
    access_level = models.CharField(max_length=20, choices=AccessLevel.choices, default=AccessLevel.CENTRE)

    # Définition des related_name pour éviter les conflits avec auth.User
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="utilisateur_groups",
        blank=True
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="utilisateur_permissions",
        blank=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class PatientManager(BaseUserManager):
    def create_user(self, code_patient, password=None, **extra_fields):
        if not code_patient:
            raise ValueError("Le code patient est obligatoire")
        user = self.model(code_patient=code_patient, **extra_fields)
        user.set_password(password or self.make_random_password())
        user.save(using=self._db)
        return user

    def create_superuser(self, code_patient, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(code_patient, password, **extra_fields)


class Patient(AbstractBaseUser, PermissionsMixin):
    code_patient = models.CharField(max_length=100, unique=True, db_index=True)
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
    numero_lot = models.CharField(max_length=100, unique=True, db_index=True)
    vaccin = models.ForeignKey(Vaccin, on_delete=models.CASCADE, related_name='lotsvaccin')
    date_fabrication = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)
    quantite_initiale = models.PositiveIntegerField()
    quantite_disponible = models.PositiveIntegerField()
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
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    consultation = models.JSONField(null=True, blank=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True, blank=True)
    maladie = models.ForeignKey(Maladie, on_delete=models.CASCADE, null=True, blank=True)


class Vaccination(models.Model):
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
    accination = models.ForeignKey('Vaccination', on_delete=models.CASCADE)
    utilisateur = models.ForeignKey('Utilisateur', on_delete=models.CASCADE)
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
    nationnalite = models.TextField()
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
