"""Integraciones opcionales de notificacion con contenido minimo."""

from __future__ import annotations

import html
import logging
import os
from urllib.parse import urlparse

import httpx


_LOGGER = logging.getLogger(__name__)
_RESEND_URL = "https://api.resend.com/emails"
_SLACK_HOST = "hooks.slack.com"


def send_resend_fallback(
    *,
    ticket_number: str,
    category: str,
    priority: str,
    question: str,
    diagnosis: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    failure_class: list[str] | None = None,
) -> str:
    """Envía los datos mínimos del ticket al respaldo Resend configurado."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("RESEND_FROM", "").strip()
    recipient = os.getenv("RESEND_TO_EMAIL", "").strip()
    if not any((api_key, sender, recipient)):
        if failure_class is not None:
            failure_class[:] = ["not_configured"]
        return "not_configured"
    if not all((api_key, sender, recipient)):
        if failure_class is not None:
            failure_class[:] = ["configuration"]
        _LOGGER.warning("Resend tiene configuracion incompleta; no se envio el respaldo.")
        return "failed"

    subject = f"[{priority.upper()}] [{ticket_number}] Incidencia - {category}"
    text = (
        f"Ticket: {ticket_number}\n"
        f"Prioridad: {priority}\n"
        f"Categoria: {category}\n"
        f"Contacto: {contact_name} ({contact_email}, {contact_phone})\n\n"
        f"Problema: {question}\n\n"
        f"Motivo de escalacion: {diagnosis}\n"
    )
    safe = html.escape
    html_content = (
        "<main><h1>Incidencia para revision tecnica</h1>"
        f"<p><strong>Ticket:</strong> {safe(ticket_number)}</p>"
        f"<p><strong>Prioridad:</strong> {safe(priority)}</p>"
        f"<p><strong>Categoria:</strong> {safe(category)}</p>"
        f"<p><strong>Contacto:</strong> {safe(contact_name)} "
        f"({safe(contact_email)}, {safe(contact_phone)})</p>"
        f"<p><strong>Problema:</strong><br>{safe(question).replace(chr(10), '<br>')}</p>"
        f"<p><strong>Motivo:</strong><br>{safe(diagnosis).replace(chr(10), '<br>')}</p>"
        "</main>"
    )
    try:
        response = httpx.post(
            _RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": sender,
                "to": [recipient],
                "cc": [contact_email],
                "subject": subject,
                "text": text,
                "html": html_content,
            },
            timeout=8,
        )
    except httpx.RequestError as exc:
        if failure_class is not None:
            failure_class[:] = ["transient"]
        _LOGGER.warning(
            "Fallo de transporte Resend; error_type=%s",
            type(exc).__name__,
        )
        return "failed"
    if not 200 <= response.status_code < 300:
        if failure_class is not None:
            failure_class[:] = [
                "configuration"
                if response.status_code in {401, 403}
                or 400 <= response.status_code < 500
                else "transient"
            ]
        _LOGGER.warning(
            "Resend rechazo el envio; status_code=%s",
            response.status_code,
        )
        return "failed"
    if failure_class is not None:
        failure_class[:] = ["none"]
    return "sent"


def send_slack_priority_alert(
    *,
    ticket_number: str,
    category: str,
    priority: str,
) -> str:
    """Notifica prioridades altas sin incluir descripcion ni datos personales."""
    if priority.casefold() not in {"high", "critical"}:
        return "skipped"
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return "not_configured"
    parsed = urlparse(webhook_url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != _SLACK_HOST
        or not parsed.path.startswith("/services/")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        _LOGGER.warning("La URL del webhook Slack no pertenece al endpoint permitido.")
        return "failed"
    try:
        response = httpx.post(
            webhook_url,
            json={
                "text": (
                    f"Ticket {ticket_number} requiere revision: "
                    f"prioridad {priority}; categoria {category}."
                )
            },
            timeout=5,
        )
    except httpx.RequestError as exc:
        _LOGGER.warning(
            "Fallo de transporte del aviso Slack; error_type=%s",
            type(exc).__name__,
        )
        return "failed"
    if not 200 <= response.status_code < 300:
        _LOGGER.warning(
            "Slack rechazo el aviso; status_code=%s",
            response.status_code,
        )
        return "failed"
    return "sent"
