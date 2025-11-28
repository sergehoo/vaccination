from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from inhp.models import Vaccination, LotVaccin, Patient, CentreVaccination, Vaccin, Mapi, AccessLevel, \
    RendezVousVaccination
from django.utils.translation import gettext_lazy as _

from pev.models import PEVCampaignTeam, PEVCampaign


class VaccinationForm(forms.ModelForm):
    class Meta:
        model = Vaccination
        fields = [
            'patient', 'centre', 'date_vaccination', 'vaccin', 'lot',
            'dose', 'date_rappel', 'created_by'
        ]
        widgets = {
            'date_vaccination': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_rappel': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'centre': forms.Select(attrs={'class': 'form-control'}),
            'vaccin': forms.Select(attrs={'class': 'form-control'}),
            'lot': forms.Select(attrs={'class': 'form-control'}),
            'dose': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'created_by': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les lots disponibles selon le vaccin sélectionné
        if 'vaccin' in self.data:
            try:
                vaccin_id = int(self.data.get('vaccin'))
                self.fields['lot'].queryset = LotVaccin.objects.filter(vaccin_id=vaccin_id, quantite_disponible__gt=0)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.vaccin:
            self.fields['lot'].queryset = LotVaccin.objects.filter(vaccin=self.instance.vaccin)
        else:
            self.fields['lot'].queryset = LotVaccin.objects.none()


# forms.py


class VaccinationFilterForm(forms.Form):
    # 🔹 Champ texte patient (code, nom, téléphone…)
    patient = forms.CharField(
        required=False,
        label="Patient",
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 "
                     "border border-slate-200/70 dark:border-slate-700/70 "
                     "px-3 py-2 text-[12px] focus:outline-none focus:ring-1 "
                     "focus:ring-ivoireBlue/70 focus:border-ivoireBlue/70",
            "placeholder": "Code, nom, prénom ou téléphone…",
        })
    )

    centre = forms.ModelChoiceField(
        queryset=CentreVaccination.objects.none(),  # ⚠️ important : on override dans __init__
        required=False,
        label="Centre de vaccination",
        widget=forms.Select(attrs={
            "class": "select2-field w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 "
                     "border border-slate-200/70 dark:border-slate-700/70 "
                     "px-3 py-2 text-[12px]",
            "data-placeholder": "Tous les centres",
        })
    )

    vaccin = forms.ModelChoiceField(
        queryset=Vaccin.objects.all(),
        required=False,
        label="Vaccin",
        widget=forms.Select(attrs={
            "class": "select2-field w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 "
                     "border border-slate-200/70 dark:border-slate-700/70 "
                     "px-3 py-2 text-[12px]",
            "data-placeholder": "Tous les vaccins",
        })
    )

    date_debut = forms.DateField(
        required=False,
        label="Date de début",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 "
                     "border border-slate-200/70 dark:border-slate-700/70 "
                     "px-3 py-2 text-[12px]",
        })
    )

    date_fin = forms.DateField(
        required=False,
        label="Date de fin",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 "
                     "border border-slate-200/70 dark:border-slate-700/70 "
                     "px-3 py-2 text-[12px]",
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        """
        On passe user depuis la vue pour restreindre les centres selon son access_level.
        """
        super().__init__(*args, **kwargs)

        qs = CentreVaccination.objects.all()

        if user is not None and hasattr(user, "access_level"):
            # from .choices import AccessLevel  # adapte l'import si besoin

            # CENTRE : uniquement son centre
            if user.access_level == AccessLevel.CENTRE and getattr(user, "centre_id", None):
                qs = qs.filter(id=user.centre_id)

            # DISTRICT : tous les centres du district
            elif user.access_level == AccessLevel.DISTRICT and getattr(user, "district_id", None):
                qs = qs.filter(district_id=user.district_id)

            # REGION : tous les centres de la région
            elif user.access_level == AccessLevel.REGION and getattr(user, "region_id", None):
                qs = qs.filter(district__region_id=user.region_id)

            # POLE : tous les centres des régions du pôle
            elif user.access_level == AccessLevel.POLE and getattr(user, "pole_id", None):
                qs = qs.filter(district__region__poles_id=user.pole_id)

            # NATIONAL : on garde tous les centres (qs initial)

        self.fields["centre"].queryset = qs.order_by("name")


class MapiPatientForm(forms.ModelForm):
    """
    Formulaire simplifié pour déclaration de MAPI par le patient.
    On ne laisse PAS le patient choisir centre/patient/date directement.
    """

    vaccination = forms.ModelChoiceField(
        queryset=Vaccination.objects.none(),
        label=_("Vaccination concernée"),
        help_text=_("Choisissez la dose pour laquelle vous avez eu un effet indésirable."),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    symptome = forms.CharField(
        label=_("Symptômes ressentis"),
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea",
                "placeholder": _("Décrivez les symptômes (douleur, fièvre, malaise, etc.)")
            }
        )
    )

    commentaire = forms.CharField(
        label=_("Commentaire / contexte (facultatif)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea",
                "placeholder": _("Ajoutez tout détail utile (délais d'apparition, médicaments pris, etc.)")
            }
        )
    )

    class Meta:
        model = Mapi
        fields = ["vaccination", "symptome", "commentaire"]

    def __init__(self, *args, **kwargs):
        patient = kwargs.pop("patient", None)
        super().__init__(*args, **kwargs)

        if patient is not None:
            # ⚠️ on limite la liste des vaccinations à celles du patient connecté
            self.fields["vaccination"].queryset = (
                Vaccination.objects.filter(patient=patient, deleted_at__isnull=True)
                .select_related("vaccin", "centre")
                .order_by("-date_vaccination")
            )
            self.fields["vaccination"].label_from_instance = (
                lambda v: f"{v.vaccin.nom if v.vaccin else 'Vaccin inconnu'} "
                          f"- dose {v.dose} du {v.date_vaccination:%d/%m/%Y} "
                          f"({v.centre.name if v.centre else 'Centre non renseigné'})"
            )


class RendezVousVaccinationForm(forms.ModelForm):
    """
    Formulaire RDV pour l'espace patient.
    """
    date_heure = forms.SplitDateTimeField(
        widget=forms.SplitDateTimeWidget(
            date_attrs={'type': 'date', 'class': 'form-control'},
            time_attrs={'type': 'time', 'class': 'form-control'},
        ),
        label="Date et heure du rendez-vous"
    )

    class Meta:
        model = RendezVousVaccination
        fields = ['centre', 'service', 'type_rdv', 'date_heure', 'motif']
        widgets = {
            'centre': forms.Select(attrs={'class': 'form-control'}),
            'service': forms.Select(attrs={'class': 'form-control'}),
            'type_rdv': forms.Select(attrs={'class': 'form-control'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        patient = kwargs.pop("patient", None)
        super().__init__(*args, **kwargs)

        # Option : pré-remplir le centre avec centre_actuel
        if patient and getattr(patient, "centre_actuel", None):
            self.fields["centre"].initial = patient.centre_actuel

    def clean_date_heure(self):
        dt = self.cleaned_data['date_heure']

        if dt <= timezone.now():
            raise ValidationError("La date du rendez-vous ne peut pas être dans le passé.")

        # Limiter à 3 mois à l’avance par exemple
        if dt > timezone.now() + timezone.timedelta(days=90):
            raise ValidationError("La date du rendez-vous ne peut pas dépasser 3 mois.")
        return dt


class AnnulationRendezVousForm(forms.Form):
    motif_annulation = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Pourquoi souhaitez-vous annuler ce rendez-vous ?'
            }
        ),
        label="Motif d'annulation"
    )

    def clean_motif_annulation(self):
        motif = self.cleaned_data['motif_annulation']
        if len(motif.strip()) < 10:
            raise ValidationError("Veuillez fournir un motif détaillé (au moins 10 caractères).")
        return motif



class PEVCampaignTeamForm(forms.ModelForm):
    class Meta:
        model = PEVCampaignTeam
        fields = [
            "code",
            "nom",
            "type_equipe",
            "pole",
            "region",
            "district",
            "centre",
            "responsable",
            "membres",
            "telephone_contact",
            "moyen_deplacement",
            "actif",
        ]
        widgets = {
            "membres": forms.SelectMultiple(attrs={"size": 6}),
        }

    def clean(self):
        cleaned = super().clean()
        pole = cleaned.get("pole")
        region = cleaned.get("region")
        district = cleaned.get("district")
        centre = cleaned.get("centre")

        zones = [z for z in [pole, region, district, centre] if z is not None]
        if not zones:
            raise forms.ValidationError(
                "Vous devez renseigner au moins une zone (pôle, région, district ou centre)."
            )
        if len(zones) > 1:
            raise forms.ValidationError(
                "Veuillez sélectionner une seule zone principale pour l'équipe."
            )
        return cleaned

class VaccinationCampainForm(forms.ModelForm):
    class Meta:
        model = Vaccination
        fields = [
            "patient", "centre", "date_vaccination",
            "vaccin", "dose", "lot", "date_rappel",
            "campagne_pev", "equipe", "vaccinateur",
        ]

    def __init__(self, *args, request=None, campagne=None, **kwargs):
        self.request = request
        self.campagne = campagne
        super().__init__(*args, **kwargs)

        # --- ÉQUIPES / CAMPAGNE ---
        from pev.models import PEVCampaignTeam  # adapte le chemin si besoin

        if self.campagne:
            # queryset des équipes actives de la campagne
            equipes_qs = PEVCampaignTeam.objects.filter(
                campagne=self.campagne,
                actif=True,
            ).order_by("code")

            self.fields["equipe"].queryset = equipes_qs

            # ✅ pré-sélectionner l’équipe de l’utilisateur s’il est membre
            if request and request.user.is_authenticated and not self.initial.get("equipe"):
                # si ton User *est déjà* le modèle Utilisateur :
                util = getattr(request.user, "utilisateur", None) or request.user

                # si PEVCampaignTeam a un M2M "membres" vers Utilisateur :
                user_team = equipes_qs.filter(membres=util).first()
                if user_team:
                    self.initial["equipe"] = user_team
        else:
            self.fields["equipe"].queryset = PEVCampaignTeam.objects.none()

        # 🔹 patient géré par la vue via patient_id → pas requis + caché
        self.fields["patient"].required = False
        self.fields["patient"].widget = forms.HiddenInput()

        # Date par défaut = aujourd’hui
        if not self.initial.get("date_vaccination"):
            self.initial["date_vaccination"] = timezone.now().date()

        # Campagne
        if self.campagne:
            self.fields["campagne_pev"].initial = self.campagne
            self.fields["campagne_pev"].widget = forms.HiddenInput()
            self.fields["equipe"].queryset = PEVCampaignTeam.objects.filter(
                campagne=self.campagne,
                actif=True,
            ).order_by("code")
        else:
            self.fields["equipe"].queryset = PEVCampaignTeam.objects.none()

        # Centre : pas obligatoire
        self.fields["centre"].required = False

        # Vaccinateur : injecté en backend → caché
        self.fields["vaccinateur"].required = False
        self.fields["vaccinateur"].widget = forms.HiddenInput()

        # Lot pas obligatoire
        self.fields["lot"].required = False

        # Styling
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Select,
                                         forms.DateInput, forms.NumberInput)):
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = " ".join([
                    css,
                    "block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm",
                    "focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm",
                ])
class PatientQuickForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            "nom", "prenoms", "date_naissance", "sexe",
            "telephone1", "commune", "quartier",
            "nom_parent", "prenoms_parent", "telephone_parent", "lien_parente",
        ]

    def __init__(self, *args, **kwargs):
        service = kwargs.pop("service", None)
        centre = kwargs.pop("centre", None)
        created_by = kwargs.pop("created_by", None)
        super().__init__(*args, **kwargs)

        for f in self.fields.values():
            f.widget.attrs.setdefault("class",
                "block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm "
                "focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            )

        # Rendre certains champs requis
        self.fields["nom"].required = True
        self.fields["prenoms"].required = True
        self.fields["date_naissance"].required = True
        self.fields["sexe"].required = True

        self._service = service
        self._centre = centre
        self._created_by = created_by

    def save(self, commit=True):
        patient = super().save(commit=False)

        # Génération simple d’un code patient (à améliorer avec un helper global)
        if not patient.code_patient:
            base = f"{patient.nom[:3].upper()}{patient.prenoms[:3].upper()}"
            from django.utils.crypto import get_random_string
            patient.code_patient = f"{base}-{get_random_string(6).upper()}"

        if self._service:
            patient.service = self._service
        if self._centre:
            patient.centre_actuel = self._centre
            patient.centre = self._centre
        if self._created_by:
            patient.created_by = self._created_by

        if commit:
            patient.save()
        return patient

