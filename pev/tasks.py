# tasks.py
from celery import shared_task
from celery.beat import logger
from django.utils import timezone
from django.conf import settings
from .models import PEVCampaignTeam, Utilisateur
from .sms_notify import send_sms


# @shared_task
# def notify_team_assignment(team_id, user_ids):
#     logger.info(f"🔔 notify_team_assignment(team_id={team_id}, user_ids={user_ids})")
#
#     try:
#         team = PEVCampaignTeam.objects.select_related("campagne").get(pk=team_id)
#     except PEVCampaignTeam.DoesNotExist:
#         logger.error(f"❌ Equipe introuvable (id={team_id})")
#         return
#
#     users = (
#         Utilisateur.objects.filter(pk__in=user_ids, is_active=True)
#         .exclude(phone__isnull=True)
#         .exclude(phone__exact="")
#     )
#
#     logger.info(f"👥 Utilisateurs éligibles trouvés : {users.count()}")
#
#     if not users.exists():
#         logger.warning("⚠️ Aucun utilisateur avec téléphone actif pour cette équipe.")
#         return
#
#     campagne = team.campagne
#     date_debut = campagne.date_debut.strftime("%d/%m/%Y") if campagne.date_debut else ""
#     date_fin = campagne.date_fin.strftime("%d/%m/%Y") if campagne.date_fin else ""
#
#     # Construire le message *une seule fois*
#     message = (
#         f"Bonjour,\n\n"
#         f"Vous avez été assigné(e) à l'équipe '{team.code} - {team.nom}' "
#         f"dans la campagne PEV '{campagne.nom}' "
#         f"({date_debut} - {date_fin}).\n\n"
#         f"Merci de votre engagement."
#     )
#
#     # Récupérer tous les numéros
#     numbers = [u.phone for u in users]
#     logger.info(f"📱 Numéros à notifier : {numbers}")
#
#     # Appel SMS (avec logs internes)
#     send_sms(numbers, message)
#
#     logger.info(f"✅ notify_team_assignment terminé pour team_id={team_id}")
#
@shared_task(bind=True)
def notify_team_assignment(self, team_id, user_ids):
    logger.info(
        "[notify_team_assignment] START team_id=%s user_ids=%s",
        team_id,
        user_ids,
    )

    try:
        team = PEVCampaignTeam.objects.select_related("campagne").get(pk=team_id)
    except PEVCampaignTeam.DoesNotExist:
        logger.error("[notify_team_assignment] Team %s introuvable", team_id)
        return

    users = (
        Utilisateur.objects.filter(pk__in=user_ids, is_active=True)
        .exclude(phone__isnull=True)
        .exclude(phone__exact="")
    )

    logger.info(
        "[notify_team_assignment] %s utilisateur(s) avec téléphone pour team=%s",
        users.count(),
        team_id,
    )

    campagne = team.campagne
    date_debut = campagne.date_debut.strftime("%d/%m/%Y") if campagne.date_debut else ""
    date_fin = campagne.date_fin.strftime("%d/%m/%Y") if campagne.date_fin else ""

    for user in users:
        message = (
            f"Bonjour {user.first_name},\n\n"
            f"Vous avez été assigne(e) a l'equipe '{team.code} - {team.nom}' "
            f"dans la campagne'{campagne.nom}' "
            f"({date_debut} - {date_fin}).\n\n"
            f"Merci de votre engagement."

        )
        logger.info(
            "[notify_team_assignment] Envoi SMS a user=%s phone=%s",
            user.id,
            user.phone,
        )
        send_sms(user.phone, message)

    logger.info("[notify_team_assignment] DONE team_id=%s", team_id)