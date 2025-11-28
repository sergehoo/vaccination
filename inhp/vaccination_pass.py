from __future__ import annotations

from django.utils import timezone
from .models import VaccinationPassEvent, Patient

def record_pass_scan(
    *,
    patient: Patient,
    service=None,
    centre=None,
    utilisateur=None,
    request=None,
    type_evenement=VaccinationPassEvent.EventType.SCAN,
    commentaire: str = "",
    meta: dict | None = None,
):
    """À appeler à chaque scan du QR Code / carnet."""

    ip = None
    ua = None
    if request is not None:
        ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT")

    event = VaccinationPassEvent.objects.create(
        patient=patient,
        type_evenement=type_evenement,
        service=service,
        centre=centre,
        utilisateur=utilisateur,
        source="portail_web",
        adresse_ip=ip,
        user_agent=ua,
        commentaire=commentaire,
        meta=meta or {},
    )

    # Met à jour la dernière date de scan
    patient.last_pass_scan_at = timezone.now()
    patient.save(update_fields=["last_pass_scan_at"])

    # Notifier le patient si autorisé
    if patient.notify_on_pass_scan:
        notifier_patient_pass_scan(patient, event)

    return event


def notifier_patient_pass_scan(patient: Patient, event: VaccinationPassEvent):
    """
    Centralise la logique d'alerte (SMS, email, push…)
    À adapter selon ton infra de notification.
    """

    message = (
        f"Bonjour {patient.prenoms}, votre carnet/pass vaccinal a été consulté "
        f"le {event.created_at:%d/%m/%Y à %H:%M} "
    )
    if event.centre:
        message += f"au centre {event.centre.name}. "
    if event.service:
        message += f"(service {event.service.nom})."

    # Exemple placeholder : SMS / Email / Notification
    # send_sms(patient.telephone1, message)
    # send_email(patient.email, "Carnet vaccinal consulté", message)
    # create_in_app_notification(patient, message)
    pass