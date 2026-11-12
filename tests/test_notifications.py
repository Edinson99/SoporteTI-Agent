import httpx

from app.notifications import send_resend_fallback, send_slack_priority_alert


def _ticket_args():
    return {
        "ticket_number": "STI-20261111-000001",
        "category": "software",
        "priority": "high",
        "question": "La aplicación se cierra al iniciar",
        "diagnosis": "No hay guía local.",
        "contact_name": "Ana",
        "contact_email": "ana@example.com",
        "contact_phone": "+57 300 123 4567",
    }


def test_resend_fallback_envia_solo_al_destino_tecnico_y_escapa_html(
    monkeypatch,
):
    monkeypatch.setenv("RESEND_API_KEY", "secret")
    monkeypatch.setenv("RESEND_FROM", "Soporte <soporte@example.com>")
    monkeypatch.setenv("RESEND_TO_EMAIL", "tecnico@example.com")
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"id": "message-id"})

    monkeypatch.setattr("app.notifications.httpx.post", post)

    result = send_resend_fallback(
        **{
            **_ticket_args(),
            "question": "<script>alert(1)</script>",
        }
    )

    assert result == "sent"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["json"]["to"] == ["tecnico@example.com"]
    assert captured["json"]["cc"] == ["ana@example.com"]
    assert "ana@example.com" not in captured["json"]["to"]
    assert "&lt;script&gt;" in captured["json"]["html"]
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert "secret" not in captured["json"]["text"]


def test_resend_fallback_reporta_configuracion_parcial(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "secret")
    monkeypatch.delenv("RESEND_FROM", raising=False)
    monkeypatch.delenv("RESEND_TO_EMAIL", raising=False)

    assert send_resend_fallback(**_ticket_args()) == "failed"


def test_resend_distingue_fallo_de_credenciales_y_fallo_transitorio(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "secret")
    monkeypatch.setenv("RESEND_FROM", "Soporte <soporte@example.com>")
    monkeypatch.setenv("RESEND_TO_EMAIL", "tecnico@example.com")
    failure = []
    monkeypatch.setattr(
        "app.notifications.httpx.post",
        lambda *_args, **_kwargs: httpx.Response(401, text="unauthorized"),
    )

    assert send_resend_fallback(**_ticket_args(), failure_class=failure) == "failed"
    assert failure == ["configuration"]

    failure.clear()
    monkeypatch.setattr(
        "app.notifications.httpx.post",
        lambda *_args, **_kwargs: httpx.Response(503, text="unavailable"),
    )

    assert send_resend_fallback(**_ticket_args(), failure_class=failure) == "failed"
    assert failure == ["transient"]


def test_slack_solo_alerte_prioridad_alta_con_datos_minimos(monkeypatch):
    monkeypatch.setenv(
        "SLACK_WEBHOOK_URL",
        "https://hooks.slack.com/services/T000/B000/test",
    )
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(200, text="ok")

    monkeypatch.setattr("app.notifications.httpx.post", post)

    result = send_slack_priority_alert(
        ticket_number="STI-20261111-000001",
        category="software",
        priority="high",
    )

    assert result == "sent"
    assert captured["json"] == {
        "text": "Ticket STI-20261111-000001 requiere revision: "
        "prioridad high; categoria software."
    }
    assert "question" not in captured["json"]["text"]
    assert send_slack_priority_alert(
        ticket_number="STI-20261111-000001",
        category="software",
        priority="normal",
    ) == "skipped"


def test_slack_rechaza_urls_fuera_del_host_aprobado(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.com/services/secret")

    assert send_slack_priority_alert(
        ticket_number="STI-20261111-000001",
        category="software",
        priority="critical",
    ) == "failed"
