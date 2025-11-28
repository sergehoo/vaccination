# inhp/mixins.py
import logging

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from inhp.models import Patient
from django.contrib.auth import get_user_model

UserModel = get_user_model()

logger = logging.getLogger(__name__)


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


class ServiceScopedMixin:
    """
    Mixin pour la gestion multi-services avec permissions avancées.
    À utiliser sur les ListView / DetailView / UpdateView des modèles
    qui ont un champ `service = ForeignKey(ServiceVaccination)`.
    """
    service_field_name = "service"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Si l'utilisateur n'a pas d'attribut service, on bloque
        if not hasattr(user, 'service'):
            return qs.none()

        service_field = self.service_field_name

        # Vérification du modèle
        if not hasattr(qs.model, service_field):
            # soit on bloque, soit on lève une erreur explicite
            # return qs.none()
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} utilisé sur un modèle sans champ '{service_field}'"
            )

        # 1) Super admin : accès complet
        if user.is_superuser:
            return qs

        # 2) Staff national sans service spécifique : accès complet
        if user.is_staff and not user.service:
            return qs

        # 3) Gestionnaire / admin de service : accès à tout le service
        if user.service and user.role in ['admin', 'gestionnaire']:
            return qs.filter(**{service_field: user.service})

        # 4) Personnel soignant : accès restreint
        if user.service and user.role in ['medecin', 'infirmier']:
            base_filter = {service_field: user.service}

            # Si le modèle possède un champ `personnel_affecte`
            if hasattr(qs.model, 'personnel_affecte'):
                return qs.filter(
                    Q(**base_filter) &
                    (Q(personnel_affecte=user) | Q(personnel_affecte__isnull=True))
                )

            return qs.filter(**base_filter)

        # 5) Tout le reste : pas d'accès
        return qs.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_service'] = getattr(self.request.user, 'service', None)
        return context


class ServiceScopedViewSetMixin:
    """
    Mixin avancé pour la gestion du scope multi-services dans les ViewSets.
    Supporte les permissions granulaires, le filtrage dynamique et l'audit.
    """

    service_field_name = "service"
    enable_audit_log = True
    strict_service_scope = True  # Si False, tu peux assouplir certains cas

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Vérifier si le modèle a un champ service
        if not hasattr(qs.model, self.service_field_name):
            logger.warning(
                f"Model {qs.model.__name__} n'a pas de champ '{self.service_field_name}'. "
                f"Scope service ignoré."
            )
            return qs

        # Super admin - accès complet
        if user.is_superuser:
            if self.enable_audit_log:
                logger.info(f"Superuser {user} accède à tous les services")
            return qs

        # Staff national sans service spécifique
        if user.is_staff and not getattr(user, 'service', None):
            if self.enable_audit_log:
                logger.info(f"Staff national {user} accède à tous les services")
            return qs

        # Utilisateur sans service
        if not getattr(user, 'service', None):
            if self.enable_audit_log:
                logger.warning(f"Utilisateur {user} sans service - accès refusé")
            return qs.none() if self.strict_service_scope else qs

        # Filtrage par service
        service_filter = {self.service_field_name: user.service}

        if self.enable_audit_log:
            logger.info(f"Utilisateur {user} accède au service {user.service}")

        return qs.filter(**service_filter)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['current_service'] = getattr(self.request.user, 'service', None)
        return context

    def perform_create(self, serializer):
        user = self.request.user

        # Superuser / staff national : on laisse le comportement par défaut
        if user.is_superuser or (user.is_staff and not getattr(user, 'service', None)):
            return super().perform_create(serializer)

        service = getattr(user, 'service', None)
        if not service:
            raise PermissionDenied("Aucun service associé à l'utilisateur.")

        # Force le service = service de l'utilisateur
        serializer.save(**{self.service_field_name: service})

    def check_service_permissions(self, obj=None):
        """
        Vérification avancée des permissions au niveau du service.
        """
        user = self.request.user

        # Super admin et staff national bypass
        if user.is_superuser or (user.is_staff and not getattr(user, 'service', None)):
            return True

        if obj and hasattr(obj, self.service_field_name):
            obj_service = getattr(obj, self.service_field_name)
            user_service = getattr(user, 'service', None)

            if obj_service != user_service:
                logger.warning(
                    f"Tentative d'accès cross-service: {user} -> {obj_service} (user: {user_service})"
                )
                return False

        return True


class ServiceScopedPermission(permissions.BasePermission):
    """
    Permission personnalisée pour la gestion multi-services.
    """

    def has_permission(self, request, view):
        user = request.user

        # Accès public
        if getattr(view, 'allow_public_access', False):
            return True

        if not user.is_authenticated:
            return False

        # Super admin / staff national
        if user.is_superuser or (user.is_staff and not getattr(user, 'service', None)):
            return True

        # Doit avoir un service
        if not getattr(user, 'service', None):
            return False

        # Lecture vs écriture
        if request.method in permissions.SAFE_METHODS:
            return self.has_read_permission(user, view)
        return self.has_write_permission(user, view)

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Super admin / staff national
        if user.is_superuser or (user.is_staff and not getattr(user, 'service', None)):
            return True

        # Vérification du scope service
        service_field = getattr(view, 'service_field_name', 'service')
        if hasattr(obj, service_field):
            obj_service = getattr(obj, service_field)
            user_service = getattr(user, 'service', None)

            if obj_service != user_service:
                logger.warning(
                    f"Permission refusée: {user} tente d'accéder à l'objet {obj} "
                    f"du service {obj_service} (user service: {user_service})"
                )
                return False

        return True

    def has_read_permission(self, user, view):
        # Simple : tous les users avec service peuvent lire
        return bool(getattr(user, 'service', None))

    def has_write_permission(self, user, view):
        write_roles = getattr(
            view,
            'allowed_write_roles',
            ['admin', 'gestionnaire', 'medecin', 'infirmier']
        )
        return getattr(user, 'role', None) in write_roles
