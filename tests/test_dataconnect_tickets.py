import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.dataconnect_tickets import (
    DataConnectError,
    FirebaseDataConnectTicketService,
)


REQUEST_ID = "45038ee8-92a5-4db4-b4b2-965983e367de"


def _service(monkeypatch, execute):
    service = FirebaseDataConnectTicketService()
    service.node = "node"
    monkeypatch.setattr(service, "_execute", execute)
    return service


def _row(request_id=REQUEST_ID, status="open", email_status="sent"):
    created_at = datetime(2026, 10, 27, tzinfo=timezone.utc).isoformat()
    ticket_number = f"STI-20261027-{request_id}"
    return {
        "id": request_id,
        "requestId": request_id,
        "contactName": "Javier Perez",
        "contactEmail": "javier@example.com",
        "contactPhone": "+57 300 123 4567",
        "queryText": "La aplicacion interna se cierra al iniciar",
        "contextJson": json.dumps(
            {
                "context": {"operating_system": "Windows 11"},
                "diagnosis": "No hay guia.",
                "email_status": email_status,
                "ticket_number": ticket_number,
                "user_id": "USR-1042",
            }
        ),
        "category": "software",
        "priority": "normal",
        "status": status,
        "resolutionNote": "Solucion aplicada." if status == "resolved" else None,
        "emailSentStatus": email_status == "sent",
        "createdAt": created_at,
        "updatedAt": created_at,
        "ticketMessages_on_ticket": [
            {
                "id": "message-1",
                "senderType": "user",
                "content": "El problema empezo hoy",
                "timestamp": created_at,
            },
            {
                "id": "message-2",
                "senderType": "user",
                "content": "La aplicacion interna se cierra al iniciar",
                "timestamp": created_at,
            },
        ],
        "ticketAuditEvents_on_ticket": [],
    }


def test_crea_ticket_atomico_con_mensajes_y_auditoria(monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    calls = []

    def execute(operation, variables):
        calls.append((operation, variables))
        return {}

    service = _service(monkeypatch, execute)
    result = service.create_ticket(
        request_id=REQUEST_ID,
        question="La aplicacion interna se cierra al iniciar",
        user_id="USR-1042",
        category="software",
        priority="normal",
        diagnosis="No se encontro una guia relacionada.",
        context={"operating_system": "Windows 11"},
        history=[{"role": "user", "content": "El problema empezo hoy"}],
        contact_name="Javier Perez",
        contact_email="javier@example.com",
        contact_phone="+57 300 123 4567",
    )

    create_call = calls[0]
    assert create_call[0] == "create_ticket"
    ticket = create_call[1]["ticket"]
    expected_number = f"STI-{datetime.fromisoformat(ticket['createdAt']):%Y%m%d}-{REQUEST_ID}"
    assert result["incident_id"] == expected_number
    assert result["ticket_email_status"] == "not_configured"
    assert ticket["id"] == REQUEST_ID
    assert ticket["requestId"] == REQUEST_ID
    metadata = json.loads(ticket["contextJson"])
    assert metadata["user_id"] == "USR-1042"
    assert metadata["diagnosis"] == "No se encontro una guia relacionada."
    assert [message["content"] for message in create_call[1]["messages"]] == [
        "El problema empezo hoy",
        "La aplicacion interna se cierra al iniciar",
    ]
    assert len(create_call[1]["events"]) == 2
    assert calls[1][0] == "update_email_status"


def test_reintento_idempotente_devuelve_ticket_sin_reenviar_correo(monkeypatch):
    calls = []
    existing = _row()

    def execute(operation, _):
        calls.append(operation)
        if operation == "create_ticket":
            raise DataConnectError("duplicate key")
        if operation == "get_ticket":
            return {"ticket": existing}
        raise AssertionError(operation)

    monkeypatch.setattr(
        "app.dataconnect_tickets.TicketService._send_email",
        lambda **_: pytest.fail("No debe reenviar el correo en un reintento"),
    )
    service = _service(monkeypatch, execute)
    result = service.create_ticket(
        request_id=REQUEST_ID,
        question="La aplicacion interna se cierra al iniciar",
        user_id="USR-1042",
        category="software",
        priority="normal",
        diagnosis="No hay guia.",
        context={},
        history=[],
        contact_name="Javier Perez",
        contact_email="javier@example.com",
        contact_phone="+57 300 123 4567",
    )

    expected_number = json.loads(existing["contextJson"])["ticket_number"]
    assert result["incident_id"] == expected_number
    assert result["ticket_email_status"] == "sent"
    assert result["status"] == "open"
    assert calls == ["create_ticket", "get_ticket"]


def test_lista_tickets_y_reconstruye_conversacion():
    service = FirebaseDataConnectTicketService()
    service.node = "node"
    service._execute = lambda *_: {
        "tickets": [_row()]
    }

    result = service.list_tickets()

    assert result[0]["ticket_number"] == f"STI-20261027-{REQUEST_ID}"
    assert result[0]["user_id"] == "USR-1042"
    assert result[0]["diagnosis"] == "No hay guia."
    assert result[0]["context"] == {"operating_system": "Windows 11"}
    assert [turn["role"] for turn in result[0]["conversation"]] == ["user", "user"]


def test_resuelve_ticket_y_guarda_evento_de_auditoria():
    row = _row()
    calls = []
    service = FirebaseDataConnectTicketService()
    service.node = "node"

    def execute(operation, variables):
        calls.append((operation, variables))
        if operation == "get_ticket":
            return {"ticket": row}
        if operation == "resolve_ticket":
            row["status"] = "resolved"
            row["resolutionNote"] = variables["resolutionNote"]
            return {}
        raise AssertionError(operation)

    service._execute = execute
    result = service.resolve_ticket(
        f"STI-20261027-{REQUEST_ID}", "Solucion aplicada."
    )

    assert result is not None
    assert result["status"] == "resolved"
    assert result["resolution_note"] == "Solucion aplicada."
    assert calls[1][0] == "resolve_ticket"
    assert calls[1][1]["event"]["eventType"] == "ticket_resolved"
    assert calls[1][1]["event"]["performedBy"] == "local_panel"


def test_rechaza_numero_de_ticket_con_formato_no_reconocido():
    service = FirebaseDataConnectTicketService()
    service.node = "node"
    service._execute = lambda *_: pytest.fail("No debe consultar Data Connect")

    assert service.resolve_ticket("STI-no-existe", "") is None


@pytest.mark.parametrize(
    ("error_code", "message"),
    [
        ("ADC_CREDENTIALS_MISSING", "No se encontraron credenciales ADC."),
        ("PERMISSION_DENIED", "no tiene permisos"),
        ("UNAUTHENTICATED", "Firebase rechazó la autenticación ADC."),
    ],
)
def test_muestra_diagnostico_accionable_para_errores_de_acceso(
    monkeypatch, error_code, message
):
    service = FirebaseDataConnectTicketService()
    service.node = "node"
    monkeypatch.setattr(
        "app.dataconnect_tickets.subprocess.run",
        Mock(
            return_value=subprocess.CompletedProcess(
                args=["node"],
                returncode=1,
                stdout="",
                stderr=json.dumps({"error": error_code}),
            )
        ),
    )

    with pytest.raises(DataConnectError, match=message):
        service._execute("list_tickets", {})
