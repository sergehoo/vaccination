# inhp/decorators.py

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from inhp.models import Patient
from django.contrib.auth import get_user_model

UserModel = get_user_model()


def patient_required(view_func):
    """
    Décorateur : n'autorise que les Patients (modèle Patient).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            messages.warning(request, _("Veuillez vous connecter pour accéder à cet espace."))
            return redirect("login")

        if not isinstance(user, Patient):
            messages.error(request, _("Accès réservé à l'espace patient."))
            return redirect("login")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def professional_required(view_func):
    """
    Décorateur : n'autorise que les professionnels (AUTH_USER_MODEL = Utilisateur).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            messages.warning(request, _("Veuillez vous connecter pour accéder à cet espace."))
            return redirect("login")

        # Pro = instance du user model principal (Utilisateur) mais PAS Patient
        if isinstance(user, Patient) or not isinstance(user, UserModel):
            messages.error(request, _("Accès réservé aux professionnels de santé."))
            return redirect("login")

        return view_func(request, *args, **kwargs)

    return _wrapped_view