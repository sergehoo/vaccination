from django import forms

from inhp.models import Vaccination, LotVaccin, Patient, CentreVaccination, Vaccin


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