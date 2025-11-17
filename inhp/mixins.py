# inhp/mixins.py

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from inhp.models import Patient
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class PatientRequiredMixin(AccessMixin):
    """
    Mixin pour les vues CBV réservées aux Patients.
    """

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            messages.warning(request, _("Veuillez vous connecter pour accéder à cet espace."))
            return redirect("login")

        if not isinstance(user, Patient):
            messages.error(request, _("Accès réservé à l'espace patient."))
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)


class ProfessionalRequiredMixin(AccessMixin):
    """
    Mixin pour les vues CBV réservées aux professionnels.
    """

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            messages.warning(request, _("Veuillez vous connecter pour accéder à cet espace."))
            return redirect("login")

        if isinstance(user, Patient) or not isinstance(user, UserModel):
            messages.error(request, _("Accès réservé aux professionnels de santé."))
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)