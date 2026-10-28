import base64
import html
import json
import sqlite3
from email import policy
from email.parser import BytesParser

from app.tickets import TicketService, _PROJECT_ROOT


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
    monkeypatch.setenv("GMAIL_OAUTH_TOKEN_FILE", "")
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


def test_ticket_envia_correo_con_firma_de_gmail_api(tmp_path, monkeypatch):
    capturado = {}

    class FakeCredentials:
        valid = True

        @classmethod
        def from_authorized_user_file(cls, token_path):
            capturado["token_path"] = token_path
            return cls()

        def has_scopes(self, scopes):
            capturado["scopes"] = scopes
            return True

    class FakeCall:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    class FakeGmail:
        def users(self):
            return self

        def settings(self):
            return self

        def sendAs(self):
            return self

        def get(self, *, userId, sendAsEmail):
            capturado["send_as"] = (userId, sendAsEmail)
            return FakeCall(
                {
                    "signature": (
                        "<div>Saludos,<br><b>Javier Mu&#241;oz</b><br>"
                        "Revisi&oacute;n t&eacute;cnica</div>"
                    )
                }
            )

        def messages(self):
            return self

        def send(self, *, userId, body):
            capturado["send_message"] = (userId, body)
            return FakeCall({"id": "message-id"})

    token_file = tmp_path / "gmail-token.json"
    token_file.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("GMAIL_SENDER", raising=False)
    monkeypatch.delenv("GMAIL_TO_EMAIL", raising=False)
    monkeypatch.setenv("GMAIL_OAUTH_TOKEN_FILE", str(token_file))
    config_path = _PROJECT_ROOT / ".env"

    def load_mail_config(path):
        capturado["config_path"] = path
        monkeypatch.setenv("GMAIL_SENDER", "soporte@example.com")
        monkeypatch.setenv("GMAIL_TO_EMAIL", "tecnico@example.com")

    monkeypatch.setattr("app.tickets.load_dotenv", load_mail_config)
    monkeypatch.setattr("app.tickets.Credentials", FakeCredentials)
    monkeypatch.setattr("app.tickets.build", lambda *args, **kwargs: FakeGmail())
    malicious_question = "La aplicación del niño falla <script>alert('test')</script>"
    resultado = _create_ticket(
        TicketService(tmp_path / "tickets.sqlite3"),
        question=malicious_question,
        category="niño educación",
    )

    assert resultado["ticket_email_status"] == "sent"
    assert capturado["config_path"] == config_path
    assert capturado["token_path"] == str(token_file)
    assert "https://www.googleapis.com/auth/gmail.settings.basic" in capturado["scopes"]
    assert capturado["send_as"] == ("me", "soporte@example.com")
    raw_message = capturado["send_message"][1]["raw"]
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw_message)
    )
    assert message["From"] == "soporte@example.com"
    assert message["To"] == "tecnico@example.com"
    assert message["Cc"] == "javier@example.com"
    assert "[NORMAL]" in message["Subject"]
    assert "nino educacion" in str(message["Subject"])
    assert resultado["incident_id"] in message["Subject"]
    text_content = message.get_body(preferencelist=("plain",)).get_content()
    assert "USR-1042" in text_content
    assert "Saludos," in text_content
    assert "Javier" in text_content
    assert "Javier Perez" in text_content
    assert "Javier Munoz" in text_content
    assert "Revision tecnica" in text_content
    assert "javier@example.com" in text_content
    assert "+57 300 123 4567" in text_content
    assert "El problema empezo hoy" in text_content
    html_content = message.get_body(preferencelist=("html",)).get_content()
    assert (
        "<div>Saludos,<br><b>Javier Munoz</b><br>Revision tecnica</div>"
        in html_content
    )
    assert "Javier Munoz" in html_content
    assert "Revision tecnica" in html_content
    outgoing_content = str(message["Subject"]) + text_content + html_content
    assert not any(
        character in outgoing_content
        for character in "\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00f1"
        "\u00c1\u00c9\u00cd\u00d3\u00da\u00dc\u00d1"
    )
    assert "Requiere revision tecnica" in html_content
    assert "Descripcion del problema" in html_content
    assert "background:#102a43" in html_content
    assert (
        "La aplicacion del nino falla "
        "&lt;script&gt;alert(&#x27;test&#x27;)&lt;/script&gt;"
        in html_content
    )
    assert "<script>" not in html_content


def test_fallo_gmail_api_no_pierde_ticket_y_queda_reportado(tmp_path, monkeypatch):
    token_file = tmp_path / "gmail-token.json"
    token_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GMAIL_SENDER", "soporte@example.com")
    monkeypatch.setenv("GMAIL_TO_EMAIL", "tecnico@example.com")
    monkeypatch.setenv("GMAIL_OAUTH_TOKEN_FILE", str(token_file))

    class FakeCredentials:
        valid = True

        @classmethod
        def from_authorized_user_file(cls, _token_path):
            return cls()

        def has_scopes(self, _scopes):
            return True

    def fail_to_build(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("app.tickets.Credentials", FakeCredentials)
    monkeypatch.setattr("app.tickets.build", fail_to_build)
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
    monkeypatch.setenv("GMAIL_OAUTH_TOKEN_FILE", "")
    service = TicketService(tmp_path / "tickets.sqlite3")

    first = _create_ticket(service)
    retry = _create_ticket(service)

    assert retry == first
    assert len(service.list_tickets()) == 1


def test_resuelve_ticket_con_fecha_y_nota(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_OAUTH_TOKEN_FILE", "")
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
