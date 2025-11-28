# pev/tasks.py ou un module sms_utils.py
import copy
import logging
import time
import unicodedata
from urllib.parse import quote

import requests
from celery import shared_task
from django.conf import settings

# from inhp.models import PEVCampaignTeam, Utilisateur

logger = logging.getLogger("pev.sms")

_TOKEN_CACHE = {"value": None, "exp": 0}

ORANGE_TOKEN_URL = "https://api.orange.com/oauth/v3/token"
ORANGE_SMS_URL = "https://api.orange.com/smsmessaging/v1/outbound/{}/requests"

def get_orange_sms_token():
    if _TOKEN_CACHE["value"] and _TOKEN_CACHE["exp"] > time.time() + 30:
        return _TOKEN_CACHE["value"]

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    data = {"grant_type": "client_credentials"}

    r = requests.post(
        settings.ORANGE_TOKEN_URL,
        data=data,
        headers=headers,
        auth=(settings.ORANGE_SMS_CLIENT_ID, settings.ORANGE_SMS_CLIENT_SECRET),
        timeout=15,
    )
    if r.status_code == 401:
        logger.error("Orange OAuth 401: %s", r.text)
        raise RuntimeError(f"Orange OAuth 401: {r.text}")
    r.raise_for_status()

    payload = r.json()
    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    _TOKEN_CACHE["value"] = token
    _TOKEN_CACHE["exp"] = time.time() + expires_in

    logger.info("✅ Token Orange SMS récupéré (expire dans %ss)", expires_in)
    return token


def optimize_sms_text(text, max_length=240):
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode()
    text = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("–", "-")
    )

    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text.strip()


def send_sms(recipients, message):
    """
    recipients : str (un numéro) ou iterable de numéros
    """
    # Normaliser en liste
    if isinstance(recipients, str):
        recipients = [recipients]
    else:
        recipients = [str(r).strip() for r in recipients if r]

    if not recipients:
        logger.warning("send_sms appelé sans destinataires → skip")
        return

    token = get_orange_sms_token()

    sender_address = settings.ORANGE_SMS_SENDER.strip()
    sender_path = quote(sender_address, safe=":+")
    sms_url = settings.ORANGE_SMS_URL.format(sender_path)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    safe_text = optimize_sms_text(message)

    payload_template = {
        "outboundSMSMessageRequest": {
            "address": [],
            "senderAddress": sender_address,
            "outboundSMSTextMessage": {"message": safe_text},
            "senderName": "INHP",
        }
    }

    for number in recipients:
        payload = copy.deepcopy(payload_template)
        payload["outboundSMSMessageRequest"]["address"] = [f"tel:{number}"]

        logger.info("📨 Envoi SMS vers %s | message='%s'", number, safe_text)

        try:
            resp = requests.post(sms_url, headers=headers, json=payload, timeout=20)
            if resp.status_code in (200, 201):
                logger.info(
                    "✅ SMS Orange OK (%s) -> %s | response=%s",
                    resp.status_code,
                    number,
                    resp.text,
                )
            else:
                logger.error(
                    "❌ SMS Orange KO (%s) -> %s | body=%s",
                    resp.status_code,
                    number,
                    resp.text,
                )
        except requests.RequestException as e:
            logger.exception("❌ Exception SMS Orange vers %s : %s", number, e)