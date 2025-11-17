from django import forms

from inhp.models import Vaccination, LotVaccin, Patient, CentreVaccination, Vaccin, Mapi
from django.utils.translation import gettext_lazy as _


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
                self.fields['lot'].queryset = LotVaccin.objects.filter(vaccin_id=vaccin_id, stock__gt=0)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.vaccin:
            self.fields['lot'].queryset = LotVaccin.objects.filter(vaccin=self.instance.vaccin)
        else:
            self.fields['lot'].queryset = LotVaccin.objects.none()


class VaccinationFilterForm(forms.Form):
    patient_code = forms.CharField(
        required=False,
        label="Code patient",
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-2xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200/70 dark:border-slate-700/70 px-3 py-2 text-[12px]",
            "placeholder": "Code ou nom du patient…",
        })
    )
    centre = forms.ModelChoiceField(
        queryset=CentreVaccination.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    vaccin = forms.ModelChoiceField(
        queryset=Vaccin.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )


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