"""Persistencia local de tickets sin guia y notificacion por correo."""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
_LOGGER = logging.getLogger(__name__)


class _SignatureTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, _attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in {"br", "div", "li", "p", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"div", "li", "p", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _format_ticket_email_html(
    *,
    ticket_number: str,
    created_at: datetime,
    user_id: str,
    category: str,
    priority: str,
    question: str,
    diagnosis: str,
    context: dict[str, Any],
    conversation: list[dict[str, str]],
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    signature: str,
) -> str:
    escape = lambda value: html.escape(str(value), quote=True)
    priority_colors = {
        "critical": ("#991b1b", "#fee2e2"),
        "high": ("#9a3412", "#ffedd5"),
        "normal": ("#1d4ed8", "#dbeafe"),
        "low": ("#475569", "#e2e8f0"),
    }
    priority_foreground, priority_background = priority_colors.get(
        priority.casefold(), ("#334155", "#e2e8f0")
    )
    context_rows = "".join(
        "<tr>"
        f'<td style="padding:9px 12px;border-bottom:1px solid #e8edf4;color:#64748b;font-size:12px;width:32%">{escape(key)}</td>'
        f'<td style="padding:9px 12px;border-bottom:1px solid #e8edf4;color:#1e293b;font-size:13px">{escape(json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value)}</td>'
        "</tr>"
        for key, value in context.items()
    ) or (
        '<tr><td style="padding:10px 12px;color:#64748b;font-size:13px">'
        "Sin contexto adicional"
        "</td></tr>"
    )
    conversation_items = "".join(
        (
            '<div style="margin:0 0 12px;padding:12px 14px;border-radius:10px;'
            f'background:{"#eff6ff" if item["role"] == "user" else "#f8fafc"};'
            f'border-left:3px solid {"#2563eb" if item["role"] == "user" else "#94a3b8"}">'
            f'<div style="margin:0 0 6px;color:#475569;font-size:11px;font-weight:700">'
            f'{escape("Usuario" if item["role"] == "user" else "Asistente")}</div>'
            f'<div style="color:#1e293b;font-size:13px;line-height:1.6">{escape(item["content"]).replace(chr(10), "<br>")}</div>'
            "</div>"
        )
        for item in conversation
    ) or '<p style="color:#64748b;font-size:13px">Sin conversación registrada.</p>'
    return f"""<!doctype html>
<html lang="es">
<body style="margin:0;padding:24px 12px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#1e293b">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden">
    <tr>
      <td style="padding:24px 28px;background:#102a43;color:#ffffff;border-bottom:4px solid #22c1b5">
        <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#b9d6e8">Soporte TI · Nueva incidencia</div>
        <div style="margin-top:9px;font-size:24px;font-weight:700">Requiere revisión técnica</div>
        <div style="margin-top:10px;font-size:13px;color:#d9e7f0">{escape(ticket_number)} &nbsp;·&nbsp; {escape(created_at.strftime("%Y-%m-%d %H:%M UTC"))}</div>
      </td>
    </tr>
    <tr><td style="padding:22px 28px 8px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="padding:12px;background:#f8fafc;border:1px solid #e8edf4;border-radius:9px">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px">Categoría</div>
          <div style="margin-top:5px;font-size:14px;font-weight:700">{escape(category)}</div>
        </td>
        <td width="12"></td>
        <td style="padding:12px;background:#f8fafc;border:1px solid #e8edf4;border-radius:9px">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px">Prioridad</div>
          <div style="margin-top:5px"><span style="display:inline-block;padding:4px 9px;border-radius:999px;background:{priority_background};color:{priority_foreground};font-size:12px;font-weight:700">{escape(priority)}</span></div>
        </td>
        <td width="12"></td>
        <td style="padding:12px;background:#f8fafc;border:1px solid #e8edf4;border-radius:9px">
          <div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px">Usuario</div>
          <div style="margin-top:5px;font-size:14px;font-weight:700">{escape(user_id)}</div>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:18px 28px 6px">
      <div style="margin-bottom:10px;color:#102a43;font-size:16px;font-weight:700">Descripción del problema</div>
      <div style="padding:14px 16px;background:#f8fafc;border:1px solid #e8edf4;border-radius:10px;font-size:14px;line-height:1.65">{escape(question).replace(chr(10), "<br>")}</div>
    </td></tr>
    <tr><td style="padding:16px 28px 6px">
      <div style="margin-bottom:8px;color:#102a43;font-size:16px;font-weight:700">Motivo de escalación</div>
      <div style="color:#334155;font-size:13px;line-height:1.6">{escape(diagnosis).replace(chr(10), "<br>")}</div>
    </td></tr>
    <tr><td style="padding:16px 28px 6px">
      <div style="margin-bottom:8px;color:#102a43;font-size:16px;font-weight:700">Datos de contacto</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #e8edf4;border-radius:9px">
        <tr><td style="padding:9px 12px;color:#64748b;font-size:12px;width:32%">Nombre</td><td style="padding:9px 12px;color:#1e293b;font-size:13px">{escape(contact_name)}</td></tr>
        <tr><td style="padding:9px 12px;border-top:1px solid #e8edf4;color:#64748b;font-size:12px">Correo</td><td style="padding:9px 12px;border-top:1px solid #e8edf4;color:#1e293b;font-size:13px">{escape(contact_email)}</td></tr>
        <tr><td style="padding:9px 12px;border-top:1px solid #e8edf4;color:#64748b;font-size:12px">Teléfono</td><td style="padding:9px 12px;border-top:1px solid #e8edf4;color:#1e293b;font-size:13px">{escape(contact_phone)}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:16px 28px 6px">
      <div style="margin-bottom:8px;color:#102a43;font-size:16px;font-weight:700">Contexto del equipo</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #e8edf4;border-radius:9px">{context_rows}</table>
    </td></tr>
    <tr><td style="padding:16px 28px 8px">
      <div style="margin-bottom:10px;color:#102a43;font-size:16px;font-weight:700">Conversación</div>
      {conversation_items}
    </td></tr>
    <tr><td style="padding:18px 28px;border-top:1px solid #e8edf4;color:#64748b;font-size:11px;line-height:1.5">
      Mensaje generado por SoporteTI-Agent. Las capturas, si existen, están disponibles en el panel local y no se adjuntan a este correo.
    </td></tr>
    <tr><td style="padding:0 28px 24px;color:#334155;font-size:13px;line-height:1.5">{signature}</td></tr>
  </table>
</body>
</html>"""


class TicketService:
    """Guarda tickets SQLite y notifica al tecnico mediante Gmail API."""

    def __init__(self, database_path: Path | None = None) -> None:
        configured_path = os.getenv("SOPORTE_TICKETS_DB")
        self.database_path = database_path or Path(
            configured_path or _PROJECT_ROOT / "data" / "tickets.sqlite3"
        )

    def create_ticket(
        self,
        *,
        request_id: str,
        question: str,
        user_id: str,
        category: str,
        priority: str,
        diagnosis: str,
        context: dict[str, Any] | None,
        history: list[dict[str, str]],
        contact_name: str,
        contact_email: str,
        contact_phone: str,
        assistant_response: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        """Persiste un ticket antes de intentar enviar su correo."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc)
        conversation = [*history, {"role": "user", "content": question}]
        if assistant_response:
            conversation.append(
                {"role": "assistant", "content": assistant_response}
            )

        with sqlite3.connect(self.database_path, timeout=10) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_schema(connection)
            existing = connection.execute(
                "SELECT ticket_number, email_status, status FROM tickets WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if existing:
                return {
                    "incident_id": existing[0],
                    "ticket_email_status": existing[1],
                    "status": existing[2],
                }
            cursor = connection.execute(
                """
                INSERT INTO tickets (
                    request_id, created_at, user_id, category, priority,
                    description, diagnosis, context_json, conversation_json,
                    email_status, contact_name, contact_email, contact_phone,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    created_at.isoformat(),
                    user_id,
                    category,
                    priority,
                    question,
                    diagnosis,
                    json.dumps(context or {}, ensure_ascii=False),
                    json.dumps(conversation, ensure_ascii=False),
                    "pending",
                    contact_name,
                    contact_email,
                    contact_phone,
                    "open",
                ),
            )
            ticket_number = f"STI-{created_at:%Y%m%d}-{cursor.lastrowid:06d}"
            connection.execute(
                "UPDATE tickets SET ticket_number = ? WHERE id = ?",
                (ticket_number, cursor.lastrowid),
            )
            connection.executemany(
                """
                INSERT INTO ticket_attachments (
                    attachment_id, ticket_number, file_name, content_type, image_data
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        attachment["id"],
                        ticket_number,
                        attachment["file_name"],
                        attachment["content_type"],
                        attachment["data"],
                    )
                    for attachment in attachments or []
                ],
            )

        email_status = self._send_email(
            ticket_number=ticket_number,
            created_at=created_at,
            question=question,
            user_id=user_id,
            category=category,
            priority=priority,
            diagnosis=diagnosis,
            context=context or {},
            conversation=conversation,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
        )
        with sqlite3.connect(self.database_path, timeout=10) as connection:
            connection.execute(
                "UPDATE tickets SET email_status = ? WHERE ticket_number = ?",
                (email_status, ticket_number),
            )

        return {
            "incident_id": ticket_number,
            "ticket_email_status": email_status,
            "status": "open",
        }

    def list_tickets(self) -> list[dict[str, Any]]:
        """Devuelve tickets recientes para el panel tecnico local."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path, timeout=10) as connection:
            connection.row_factory = sqlite3.Row
            self._ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT ticket_number, created_at, user_id, category, priority,
                       description, diagnosis, context_json, conversation_json,
                       email_status, contact_name, contact_email, contact_phone,
                       status, resolved_at, resolution_note
                FROM tickets ORDER BY id DESC
                """
            ).fetchall()
            attachment_rows = connection.execute(
                """
                SELECT attachment_id, ticket_number, file_name, content_type,
                       length(image_data) AS size
                FROM ticket_attachments ORDER BY rowid
                """
            ).fetchall()
        attachments_by_ticket: dict[str, list[dict[str, Any]]] = {}
        for attachment in attachment_rows:
            attachments_by_ticket.setdefault(attachment["ticket_number"], []).append(
                {
                    "id": attachment["attachment_id"],
                    "file_name": attachment["file_name"],
                    "content_type": attachment["content_type"],
                    "size": attachment["size"],
                }
            )
        return [
            {
                **dict(row),
                "context": json.loads(row["context_json"]),
                "conversation": json.loads(row["conversation_json"]),
                "attachments": attachments_by_ticket.get(row["ticket_number"], []),
            }
            for row in rows
        ]

    def get_attachment(
        self,
        ticket_number: str,
        attachment_id: str,
    ) -> dict[str, Any] | None:
        """Lee una imagen asociada al ticket solicitado."""
        with sqlite3.connect(self.database_path, timeout=10) as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                """
                SELECT file_name, content_type, image_data
                FROM ticket_attachments
                WHERE ticket_number = ? AND attachment_id = ?
                """,
                (ticket_number, attachment_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "file_name": row[0],
            "content_type": row[1],
            "data": row[2],
        }

    def resolve_ticket(
        self,
        ticket_number: str,
        resolution_note: str,
    ) -> dict[str, str] | None:
        """Marca un ticket abierto como resuelto sin sobrescribir el cierre inicial."""
        with sqlite3.connect(self.database_path, timeout=10) as connection:
            self._ensure_schema(connection)
            connection.execute(
                """
                UPDATE tickets
                SET status = 'resolved', resolved_at = ?, resolution_note = ?
                WHERE ticket_number = ? AND status = 'open'
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    resolution_note,
                    ticket_number,
                ),
            )
            row = connection.execute(
                """
                SELECT ticket_number, status, resolved_at, resolution_note
                FROM tickets WHERE ticket_number = ?
                """,
                (ticket_number,),
            ).fetchone()
        if row is None:
            return None
        return {
            "ticket_number": row[0],
            "status": row[1],
            "resolved_at": row[2],
            "resolution_note": row[3] or "",
        }

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE,
                request_id TEXT,
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                description TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                context_json TEXT NOT NULL,
                conversation_json TEXT NOT NULL,
                email_status TEXT NOT NULL,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                resolved_at TEXT,
                resolution_note TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id TEXT NOT NULL,
                ticket_number TEXT NOT NULL,
                file_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                image_data BLOB NOT NULL,
                PRIMARY KEY (ticket_number, attachment_id)
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tickets)")
        }
        migrations = {
            "request_id": "TEXT",
            "contact_name": "TEXT",
            "contact_email": "TEXT",
            "contact_phone": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'open'",
            "resolved_at": "TEXT",
            "resolution_note": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE tickets ADD COLUMN {column} {definition}"
                )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_request_id "
            "ON tickets(request_id)"
        )

    @staticmethod
    def _send_email(
        *,
        ticket_number: str,
        created_at: datetime,
        question: str,
        user_id: str,
        category: str,
        priority: str,
        diagnosis: str,
        context: dict[str, Any],
        conversation: list[dict[str, str]],
        contact_name: str,
        contact_email: str,
        contact_phone: str,
    ) -> str:
        sender = os.getenv("GMAIL_SENDER", "").strip()
        recipient = os.getenv("GMAIL_TO_EMAIL", "").strip()
        token_path = Path(
            os.getenv("GMAIL_OAUTH_TOKEN_FILE", ".secrets/gmail-token.json")
        )
        if not token_path.is_absolute():
            token_path = _PROJECT_ROOT / token_path
        if not all((sender, recipient)) or not token_path.is_file():
            return "not_configured"

        conversation_text = "\n\n".join(
            f"{'Usuario' if item['role'] == 'user' else 'Asistente'}: {item['content']}"
            for item in conversation
        )
        context_text = "\n".join(
            f"- {key}: {value}" for key, value in context.items()
        ) or "- Sin contexto adicional"
        body_text = f"""Borrador de incidencia para revision tecnica

Ticket: {ticket_number}
Fecha UTC: {created_at.isoformat()}
Usuario indicado: {user_id}
Nombre de contacto: {contact_name}
Correo de contacto: {contact_email}
Telefono de contacto: {contact_phone}
Tema: {category}
Prioridad: {priority}

Descripcion del problema:
{question}

Motivo de escalacion:
{diagnosis}

Contexto declarado:
{context_text}

Conversacion disponible:
{conversation_text}
"""

        try:
            credentials = Credentials.from_authorized_user_file(str(token_path))
            if not credentials.has_scopes(
                [
                    "https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/gmail.settings.basic",
                ]
            ):
                raise ValueError(
                    "El token de Gmail no tiene permisos de envío y lectura de firma; "
                    "vuelve a ejecutar scripts/authorize_gmail.py."
                )
            if not credentials.valid:
                credentials.refresh(Request())
                token_path.write_text(credentials.to_json(), encoding="utf-8")

            gmail = build(
                "gmail",
                "v1",
                credentials=credentials,
                cache_discovery=False,
            )
            send_as = (
                gmail.users()
                .settings()
                .sendAs()
                .get(userId="me", sendAsEmail=sender)
                .execute()
            )
            signature = send_as.get("signature", "")

            message = EmailMessage()
            message["Subject"] = (
                f"[{priority.upper()}] [{ticket_number}] Incidencia - {category}"
            )
            message["From"] = sender
            message["To"] = recipient
            message["Cc"] = contact_email
            signature_parser = _SignatureTextParser()
            signature_parser.feed(signature)
            signature_text = "".join(signature_parser.parts).strip()
            message.set_content(
                body_text + (f"\n\n{signature_text}" if signature_text else "")
            )
            message.add_alternative(
                _format_ticket_email_html(
                    ticket_number=ticket_number,
                    created_at=created_at,
                    user_id=user_id,
                    category=category,
                    priority=priority,
                    question=question,
                    diagnosis=diagnosis,
                    context=context,
                    conversation=conversation,
                    contact_name=contact_name,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    signature=signature,
                ),
                subtype="html",
            )
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes(policy=policy.SMTP)
            ).decode("ascii")
            gmail.users().messages().send(
                userId="me", body={"raw": raw_message}
            ).execute()
        except (OSError, ValueError, GoogleAuthError, HttpError) as exc:
            _LOGGER.warning(
                "No se pudo enviar el correo Gmail del ticket %s: %s",
                ticket_number,
                exc,
            )
            return "failed"
        return "sent"
