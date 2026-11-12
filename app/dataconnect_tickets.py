"""Persistencia de tickets mediante Firebase Data Connect Admin SDK."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from app.tickets import TicketService
from app.notifications import send_resend_fallback, send_slack_priority_alert


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BRIDGE = _PROJECT_ROOT / "app" / "dataconnect_bridge.mjs"
_ATTACHMENT_RETENTION_DAYS = 180


class DataConnectError(RuntimeError):
    """Error explícito al comunicarse con Firebase Data Connect."""


class FirebaseDataConnectTicketService:
    """Guarda tickets y conversación en el servicio Data Connect configurado."""

    def __init__(self) -> None:
        configured_node = os.getenv("NODE_BIN")
        node = configured_node or shutil.which("node") or shutil.which("node.exe")
        if not node and Path(r"C:\Program Files\nodejs\node.exe").exists():
            node = r"C:\Program Files\nodejs\node.exe"
        self.node = node

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
        request_uuid = UUID(request_id)
        ticket_id = str(request_uuid)
        created_at = datetime.now(timezone.utc)
        ticket_number = self._ticket_number(created_at, request_uuid)
        conversation = [*history, {"role": "user", "content": question}]
        if assistant_response:
            conversation.append(
                {"role": "assistant", "content": assistant_response}
            )
        metadata = {
            "context": context or {},
            "diagnosis": diagnosis,
            "email_status": "pending",
            "email_provider": "none",
            "email_failure_class": "pending",
            "alert_status": "pending" if priority.casefold() in {"high", "critical"} else "skipped",
            "ticket_number": ticket_number,
            "user_id": user_id,
            "attachments": [
                {
                    "id": attachment["id"],
                    "file_name": attachment["file_name"],
                    "content_type": attachment["content_type"],
                    "size": len(attachment["data"]),
                    "data_base64": base64.b64encode(attachment["data"]).decode("ascii"),
                }
                for attachment in attachments or []
            ],
        }
        context_json = json.dumps(metadata, ensure_ascii=False)
        ticket = {
            "id": ticket_id,
            "requestId": request_id,
            "contactName": contact_name,
            "contactEmail": contact_email,
            "contactPhone": contact_phone,
            "queryText": question,
            "contextJson": context_json,
            "category": category,
            "priority": priority,
            "status": "open",
            "emailSentStatus": False,
            "createdAt": created_at.isoformat(),
            "updatedAt": created_at.isoformat(),
        }
        messages = [
            {
                "id": str(uuid5(request_uuid, f"message:{position}")),
                "ticketId": ticket_id,
                "senderType": "user" if item["role"] == "user" else "assistant",
                "content": item["content"],
            }
            for position, item in enumerate(conversation)
        ]
        events = [
            self._audit_event(
                request_uuid,
                ticket_id,
                "ticket_created",
                None,
                json.dumps({"ticket_number": ticket_number}, ensure_ascii=False),
            ),
            self._audit_event(
                request_uuid,
                ticket_id,
                "email_status",
                None,
                "pending",
                event_key="email:pending",
            ),
        ]

        try:
            self._execute(
                "create_ticket",
                {"ticket": ticket, "messages": messages, "events": events},
            )
        except DataConnectError as create_error:
            try:
                existing = self._get_ticket(ticket_id)
            except DataConnectError as lookup_error:
                raise create_error from lookup_error
            if existing is None:
                raise
            return self._create_response(existing)

        gmail_failure: list[str] = []
        email_status = TicketService._send_email(
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
            failure_class=gmail_failure,
        )
        email_provider = "gmail" if email_status == "sent" else "none"
        email_failure_class = "none" if email_status == "sent" else "not_configured"
        if email_status != "sent":
            resend_failure: list[str] = []
            resend_status = send_resend_fallback(
                ticket_number=ticket_number,
                category=category,
                priority=priority,
                question=question,
                diagnosis=diagnosis,
                contact_name=contact_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                failure_class=resend_failure,
            )
            if resend_status == "sent":
                email_status = "sent"
                email_provider = "resend"
                email_failure_class = "none"
            elif email_status == "not_configured" and resend_status == "not_configured":
                email_status = "not_configured"
                email_failure_class = "not_configured"
            else:
                email_status = "failed"
                failure_classes = [*gmail_failure, *resend_failure]
                email_failure_class = (
                    "configuration"
                    if "configuration" in failure_classes
                    else "transient"
                )
        alert_status = send_slack_priority_alert(
            ticket_number=ticket_number,
            category=category,
            priority=priority,
        )
        metadata["email_status"] = email_status
        metadata["email_provider"] = email_provider
        metadata["email_failure_class"] = email_failure_class
        metadata["alert_status"] = alert_status
        self._execute(
            "update_email_status",
            {
                "id": ticket_id,
                "emailSentStatus": email_status == "sent",
                "contextJson": json.dumps(metadata, ensure_ascii=False),
                "event": self._audit_event(
                    request_uuid,
                    ticket_id,
                    "email_status",
                    "pending",
                    email_status,
                    event_key=f"email:{email_status}",
                ),
                "alertEvent": self._audit_event(
                    request_uuid,
                    ticket_id,
                    "slack_alert_status",
                    "pending" if priority.casefold() in {"high", "critical"} else "skipped",
                    alert_status,
                    event_key=f"slack:{alert_status}",
                ),
            },
        )
        return {
            "incident_id": ticket_number,
            "ticket_email_status": email_status,
            "status": "open",
            "email_provider": email_provider,
            "email_failure_class": email_failure_class,
            "alert_status": alert_status,
        }

    def list_tickets(self) -> list[dict[str, Any]]:
        result = self._execute("list_tickets", {})
        tickets = result.get("tickets")
        if not isinstance(tickets, list):
            raise DataConnectError("Data Connect devolvió una lista de tickets inválida.")
        for ticket in tickets:
            self._expire_ticket_attachments(ticket)
        return sorted(
            (self._to_ticket(ticket) for ticket in tickets),
            key=lambda ticket: ticket["created_at"],
            reverse=True,
        )

    def resolve_ticket(
        self,
        ticket_number: str,
        resolution_note: str,
    ) -> dict[str, str] | None:
        ticket_id = self._ticket_id_from_number(ticket_number)
        if ticket_id is None:
            return None
        ticket = self._get_ticket(ticket_id)
        if ticket is None:
            return None
        self._expire_ticket_attachments(ticket)
        if ticket["status"] != "resolved":
            request_uuid = UUID(ticket_id)
            metadata = json.loads(ticket.get("contextJson") or "{}")
            metadata["attachments"] = []
            self._execute(
                "resolve_ticket",
                {
                    "id": ticket_id,
                    "resolutionNote": resolution_note,
                    "contextJson": json.dumps(metadata, ensure_ascii=False),
                    "event": self._audit_event(
                        request_uuid,
                        ticket_id,
                        "ticket_resolved",
                        "open",
                        "resolved",
                        performed_by="local_panel",
                        event_key="resolved",
                    ),
                },
            )
            ticket = self._get_ticket(ticket_id)
            if ticket is None:
                raise DataConnectError("El ticket desapareció durante su resolución.")
        return {
            "ticket_number": self._to_ticket(ticket)["ticket_number"],
            "status": ticket["status"],
            "resolved_at": ticket["updatedAt"],
            "resolution_note": ticket.get("resolutionNote") or "",
        }

    def _get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        result = self._execute("get_ticket", {"id": ticket_id})
        ticket = result.get("ticket")
        return ticket if isinstance(ticket, dict) else None

    def _expire_ticket_attachments(self, row: dict[str, Any]) -> None:
        metadata = json.loads(row.get("contextJson") or "{}")
        attachments = metadata.get("attachments")
        if not isinstance(attachments, list) or not attachments:
            return
        created_at = datetime.fromisoformat(
            row["createdAt"].replace("Z", "+00:00")
        )
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        expired = created_at <= datetime.now(timezone.utc) - timedelta(
            days=_ATTACHMENT_RETENTION_DAYS
        )
        if row.get("status") != "resolved" and not expired:
            return
        metadata["attachments"] = []
        encoded_metadata = json.dumps(metadata, ensure_ascii=False)
        self._execute(
            "update_ticket_metadata",
            {"id": row["id"], "contextJson": encoded_metadata},
        )
        row["contextJson"] = encoded_metadata

    def get_attachment(
        self,
        ticket_number: str,
        attachment_id: str,
    ) -> dict[str, Any] | None:
        """Lee una imagen adjunta al ticket consultado."""
        ticket_id = self._ticket_id_from_number(ticket_number)
        if ticket_id is None:
            return None
        row = self._get_ticket(ticket_id)
        if row is None:
            return None
        self._expire_ticket_attachments(row)
        ticket = self._to_ticket(row)
        if ticket["ticket_number"] != ticket_number:
            return None
        metadata = json.loads(row.get("contextJson") or "{}")
        for attachment in metadata.get("attachments", []):
            if attachment.get("id") == attachment_id:
                try:
                    image_data = base64.b64decode(
                        attachment["data_base64"],
                        validate=True,
                    )
                except (KeyError, ValueError) as exc:
                    raise DataConnectError(
                        "El adjunto almacenado en Firebase tiene un formato inválido."
                    ) from exc
                return {
                    "file_name": attachment["file_name"],
                    "content_type": attachment["content_type"],
                    "data": image_data,
                }
        return None

    def _execute(self, operation: str, variables: dict[str, Any]) -> dict[str, Any]:
        if not self.node:
            raise DataConnectError(
                "Node.js no está disponible. Instala Node.js LTS para usar Data Connect."
            )
        try:
            result = subprocess.run(
                [self.node, str(_BRIDGE)],
                input=json.dumps(
                    {"operation": operation, "variables": variables},
                    ensure_ascii=False,
                ),
                capture_output=True,
                text=True,
                cwd=_PROJECT_ROOT,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DataConnectError("La operación de Firebase Data Connect agotó el tiempo.") from exc
        except OSError as exc:
            raise DataConnectError("No se pudo iniciar el puente de Firebase Data Connect.") from exc

        if result.returncode:
            try:
                error_code = json.loads(result.stderr).get("error", "DATACONNECT_ERROR")
            except (json.JSONDecodeError, AttributeError):
                error_code = "DATACONNECT_ERROR"
            error_messages = {
                "ADC_CREDENTIALS_MISSING": (
                    "No se encontraron credenciales ADC. Instala Google Cloud CLI, "
                    "ejecuta `gcloud auth application-default login` y reinicia el servidor."
                ),
                "PERMISSION_DENIED": (
                    "La identidad ADC no tiene permisos para invocar este conector "
                    "de Firebase Data Connect."
                ),
                "UNAUTHENTICATED": (
                    "Firebase rechazó la autenticación ADC. Ejecuta de nuevo "
                    "`gcloud auth application-default login`."
                ),
                "INVALID_CREDENTIAL": (
                    "Las credenciales ADC no son válidas. Vuelve a autenticarte "
                    "con `gcloud auth application-default login`."
                ),
                "DATACONNECT_NOT_FOUND": (
                    "Firebase Data Connect no encontró el servicio o conector "
                    "configurado. Comprueba proyecto, ubicación e ID del servicio."
                ),
                "GRAPHQL_OPERATION_FAILED": (
                    "Data Connect rechazó la operación GraphQL. Comprueba que el "
                    "conector esté desplegado y que las variables coincidan con su esquema."
                ),
            }
            raise DataConnectError(
                error_messages.get(
                    error_code,
                    f"Falló la operación de Firebase Data Connect ({error_code}).",
                )
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DataConnectError(
                "Firebase Data Connect devolvió una respuesta inválida."
            ) from exc
        if not isinstance(payload, dict):
            raise DataConnectError("Firebase Data Connect devolvió un resultado inválido.")
        return payload

    @classmethod
    def _to_ticket(cls, row: dict[str, Any]) -> dict[str, Any]:
        metadata = json.loads(row.get("contextJson") or "{}")
        attachments = [
            {
                "id": attachment["id"],
                "file_name": attachment["file_name"],
                "content_type": attachment["content_type"],
                "size": attachment.get("size", 0),
            }
            for attachment in metadata.get("attachments", [])
        ]
        safe_metadata = {**metadata, "attachments": attachments}
        created_at = row["createdAt"]
        ticket_number = metadata.get("ticket_number") or cls._ticket_number(
            datetime.fromisoformat(created_at.replace("Z", "+00:00")),
            UUID(row["id"]),
        )
        messages = sorted(
            row.get("ticketMessages_on_ticket") or [],
            key=lambda message: message["timestamp"],
        )
        conversation = [
            {
                "role": "user" if message["senderType"] == "user" else "assistant",
                "content": message["content"],
            }
            for message in messages
        ]
        status = row["status"]
        return {
            "ticket_number": ticket_number,
            "created_at": created_at,
            "user_id": metadata.get("user_id", ""),
            "category": row["category"],
            "priority": row["priority"],
            "description": row["queryText"],
            "diagnosis": metadata.get("diagnosis", ""),
            "context_json": json.dumps(safe_metadata, ensure_ascii=False),
            "context": metadata.get("context", {}),
            "conversation_json": json.dumps(conversation, ensure_ascii=False),
            "conversation": conversation,
            "email_status": metadata.get(
                "email_status",
                "sent" if row.get("emailSentStatus") else "pending",
            ),
            "email_provider": metadata.get("email_provider", "none"),
            "email_failure_class": metadata.get(
                "email_failure_class",
                "not_configured",
            ),
            "alert_status": metadata.get("alert_status", "not_configured"),
            "contact_name": row["contactName"],
            "contact_email": row["contactEmail"],
            "contact_phone": row["contactPhone"],
            "status": status,
            "resolved_at": row["updatedAt"] if status == "resolved" else None,
            "resolution_note": row.get("resolutionNote"),
            "attachments": attachments,
        }

    @classmethod
    def _create_response(cls, row: dict[str, Any]) -> dict[str, str]:
        ticket = cls._to_ticket(row)
        return {
            "incident_id": ticket["ticket_number"],
            "ticket_email_status": ticket["email_status"],
            "status": ticket["status"],
            "email_provider": ticket["email_provider"],
            "email_failure_class": ticket["email_failure_class"],
            "alert_status": ticket["alert_status"],
        }

    @staticmethod
    def _ticket_number(created_at: datetime, request_uuid: UUID) -> str:
        return f"STI-{created_at:%Y%m%d}-{request_uuid}"

    @staticmethod
    def _ticket_id_from_number(ticket_number: str) -> str | None:
        parts = ticket_number.split("-", 2)
        if len(parts) != 3 or parts[0] != "STI":
            return None
        try:
            return str(UUID(parts[2]))
        except ValueError:
            return None

    @staticmethod
    def _audit_event(
        request_uuid: UUID,
        ticket_id: str,
        event_type: str,
        previous_value: str | None,
        new_value: str | None,
        *,
        performed_by: str = "system",
        event_key: str | None = None,
    ) -> dict[str, Any]:
        event_name = event_key or event_type
        return {
            "id": str(uuid5(request_uuid, f"audit:{event_name}")),
            "ticketId": ticket_id,
            "eventType": event_type,
            "performedBy": performed_by,
            "previousValue": previous_value,
            "newValue": new_value,
        }
