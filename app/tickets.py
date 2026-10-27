"""Persistencia local de tickets sin guia y notificacion por correo."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import sqlite3
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
_LOGGER = logging.getLogger(__name__)


class TicketService:
    """Guarda tickets SQLite y notifica al tecnico si SMTP esta configurado."""

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
        return [
            {
                **dict(row),
                "context": json.loads(row["context_json"]),
                "conversation": json.loads(row["conversation_json"]),
            }
            for row in rows
        ]

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
        sender = os.getenv("SMTP_FROM_EMAIL", "soporteitelectiva@gmail.com").strip()
        recipient = os.getenv("SMTP_TO_EMAIL", "javiercito9456@gmail.com").strip()
        username = os.getenv("SMTP_USERNAME", sender).strip()
        password = "".join(os.getenv("SMTP_APP_PASSWORD", "").split())
        if not all((sender, recipient, username, password)):
            return "not_configured"

        try:
            port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError:
            _LOGGER.warning("SMTP_PORT invalido para el ticket %s", ticket_number)
            return "failed"

        message = EmailMessage()
        message["Subject"] = f"[{ticket_number}] Incidencia sin guia - {category}"
        message["From"] = sender
        message["To"] = recipient
        conversation_text = "\n\n".join(
            f"{'Usuario' if item['role'] == 'user' else 'Asistente'}: {item['content']}"
            for item in conversation
        )
        context_text = "\n".join(
            f"- {key}: {value}" for key, value in context.items()
        ) or "- Sin contexto adicional"
        message.set_content(
            f"""Borrador de incidencia para revision tecnica

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
        )

        try:
            with smtplib.SMTP(
                os.getenv("SMTP_HOST", "smtp.gmail.com"),
                port,
                timeout=15,
            ) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            _LOGGER.warning(
                "No se pudo enviar el correo del ticket %s: %s",
                ticket_number,
                exc,
            )
            return "failed"
        return "sent"
