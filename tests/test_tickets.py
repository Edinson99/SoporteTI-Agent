import json
import sqlite3
from email.message import EmailMessage

from app.tickets import TicketService


def _create_ticket(service, **overrides):
    values = {
        "question": "La aplicacion interna se cierra al iniciar",
        "request_id": "45038ee8-92a5-4db4-b4b2-965983e367de",
        "user_id": "USR-1042",
        "category": "software",
        "priority": "normal",
        "diagnosis": "No se encontro una guia relacionada.",
        "context": {"operating_system": "Windows 11"},
        "history": [{"role": "user", "content": "El problema empezo hoy"}],
        "contact_name": "Javier Perez",
        "contact_email": "javier@example.com",
        "contact_phone": "+57 300 123 4567",
    }
    values.update(overrides)
    return service.create_ticket(**values)


def test_ticket_persistente_incluye_conversacion_y_estado_sin_correo(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    service = TicketService(tmp_path / "tickets.sqlite3")

    resultado = _create_ticket(service)
    segundo = _create_ticket(
        service,
        request_id="45038ee8-92a5-4db4-b4b2-965983e367df",
        question="El monitor parpadea",
    )

    assert resultado["incident_id"].startswith("STI-")
    assert segundo["incident_id"] != resultado["incident_id"]
    assert resultado["ticket_email_status"] == "not_configured"
    with sqlite3.connect(service.database_path) as connection:
        row = connection.execute(
            """
            SELECT user_id, category, priority, description, diagnosis,
                   context_json, conversation_json, email_status
            FROM tickets WHERE ticket_number = ?
            """,
            (resultado["incident_id"],),
        ).fetchone()
    assert row is not None
    assert row[:5] == (
        "USR-1042",
        "software",
        "normal",
        "La aplicacion interna se cierra al iniciar",
        "No se encontro una guia relacionada.",
    )
    assert json.loads(row[5]) == {"operating_system": "Windows 11"}
    assert [turn["role"] for turn in json.loads(row[6])] == ["user", "user"]
    assert row[7] == "not_configured"
    ticket = service.list_tickets()[1]
    assert ticket["contact_email"] == "javier@example.com"
    assert ticket["status"] == "open"


def test_ticket_envia_correo_gmail_por_starttls(tmp_path, monkeypatch):
    capturado = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            capturado["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def ehlo(self):
            pass

        def starttls(self, *, context):
            capturado["tls"] = context

        def login(self, username, password):
            capturado["credentials"] = (username, password)

        def send_message(self, message: EmailMessage):
            capturado["message"] = message

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "soporteitelectiva@gmail.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "soporteitelectiva@gmail.com")
    monkeypatch.setenv("SMTP_TO_EMAIL", "javiercito9456@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "abcd efgh")
    monkeypatch.setattr("app.tickets.smtplib.SMTP", FakeSMTP)
    resultado = _create_ticket(TicketService(tmp_path / "tickets.sqlite3"))

    assert resultado["ticket_email_status"] == "sent"
    assert capturado["connection"] == ("smtp.gmail.com", 587, 15)
    assert capturado["credentials"] == ("soporteitelectiva@gmail.com", "abcdefgh")
    message = capturado["message"]
    assert message["From"] == "soporteitelectiva@gmail.com"
    assert message["To"] == "javiercito9456@gmail.com"
    assert resultado["incident_id"] in message["Subject"]
    assert "USR-1042" in message.get_content()
    assert "Javier Perez" in message.get_content()
    assert "javier@example.com" in message.get_content()
    assert "+57 300 123 4567" in message.get_content()
    assert "El problema empezo hoy" in message.get_content()


def test_fallo_smtp_no_pierde_ticket_y_queda_reportado(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "fake-password")

    class FailedSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.gmail.com", 587, 15)
            raise OSError("connection refused")

    monkeypatch.setattr("app.tickets.smtplib.SMTP", FailedSMTP)
    service = TicketService(tmp_path / "tickets.sqlite3")
    resultado = _create_ticket(service)

    assert resultado["ticket_email_status"] == "failed"
    with sqlite3.connect(service.database_path) as connection:
        status = connection.execute(
            "SELECT email_status FROM tickets WHERE ticket_number = ?",
            (resultado["incident_id"],),
        ).fetchone()[0]
    assert status == "failed"


def test_repetir_solicitud_idempotente_no_duplica_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    service = TicketService(tmp_path / "tickets.sqlite3")

    first = _create_ticket(service)
    retry = _create_ticket(service)

    assert retry == first
    assert len(service.list_tickets()) == 1


def test_resuelve_ticket_con_fecha_y_nota(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    service = TicketService(tmp_path / "tickets.sqlite3")
    created = _create_ticket(service)

    result = service.resolve_ticket(created["incident_id"], "Aplicacion reinstalada.")

    assert result is not None
    assert result["status"] == "resolved"
    assert result["resolved_at"]
    assert result["resolution_note"] == "Aplicacion reinstalada."
    assert service.resolve_ticket("STI-no-existe", "") is None


def test_migra_base_previa_de_tickets(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE,
                created_at TEXT NOT NULL,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                description TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                context_json TEXT NOT NULL,
                conversation_json TEXT NOT NULL,
                email_status TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO tickets VALUES (
                1, 'STI-20261026-000001', '2026-10-26T00:00:00+00:00',
                'USR-1', 'general', 'normal', 'Descripcion', 'Diagnostico',
                '{}', '[]', 'not_configured'
            )
            """
        )

    tickets = TicketService(database).list_tickets()

    assert tickets[0]["ticket_number"] == "STI-20261026-000001"
    assert tickets[0]["status"] == "open"
    assert tickets[0]["contact_email"] is None
