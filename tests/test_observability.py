from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.observability import (
    RequestTelemetry,
    SlidingWindowRateLimiter,
    scrub_sentry_event,
)


def test_api_expone_estado_y_metricas_sin_detalles_sensibles(monkeypatch):
    for name in (
        "RESEND_API_KEY",
        "SLACK_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "SENTRY_DSN",
    ):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 8001),
    )

    status = client.get("/api/status")
    metrics = client.get("/api/metrics")
    page = client.get("/status")

    assert status.status_code == 200
    assert status.json()["status"] == "operational"
    assert status.json()["components"]["alerts"] == "not_configured"
    assert "SLACK_WEBHOOK_URL" not in status.text
    assert metrics.status_code == 200
    assert page.status_code == 200
    assert "Información desactualizada" in page.text


def test_metricas_operativas_son_solo_loopback():
    remote_client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("192.168.1.10", 8001),
    )

    assert remote_client.get("/api/metrics").status_code == 403


def test_limite_temporal_protege_ruta_de_diagnostico(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_rate_limiter",
        SlidingWindowRateLimiter(limit=1),
    )
    client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 8001),
    )
    request = {
        "question": "No tengo internet",
        "user_id": "USR-1042",
    }

    first = client.post("/agent/ask", json=request)
    limited = client.post("/agent/ask", json=request)

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_rate_limiter_rechaza_durante_ventana_y_permite_al_vencer():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)

    assert limiter.allow("127.0.0.1", "/agent/ask", now=1)
    assert limiter.allow("127.0.0.1", "/agent/ask", now=2)
    assert not limiter.allow("127.0.0.1", "/agent/ask", now=3)
    assert limiter.allow("127.0.0.1", "/agent/ask", now=11)


def test_metricas_agregan_solo_ruta_estado_y_latencia():
    telemetry = RequestTelemetry()
    telemetry.record("post", "/agent/ask", 200, 0.125)
    telemetry.record("POST", "/agent/ask", 500, 0.25)

    snapshot = telemetry.snapshot()

    assert snapshot["server_errors"] == 1
    assert snapshot["requests"] == [
        {
            "method": "POST",
            "route": "/agent/ask",
            "status_code": 200,
            "count": 1,
        },
        {
            "method": "POST",
            "route": "/agent/ask",
            "status_code": 500,
            "count": 1,
        },
    ]
    assert snapshot["latency"] == [
        {
            "method": "POST",
            "route": "/agent/ask",
            "average_ms": 187.5,
            "max_ms": 250.0,
            "count": 2,
        }
    ]
    assert "question" not in repr(snapshot)


def test_evento_sentry_elimina_mensajes_solicitudes_y_variables():
    event = {
        "event_id": "id",
        "level": "error",
        "message": "El usuario escribió datos privados",
        "request": {"data": {"question": "texto privado"}},
        "user": {"email": "persona@example.com"},
        "extra": {"secret": "token"},
        "breadcrumbs": [{"message": "texto privado"}],
        "exception": {
            "values": [
                {
                    "type": "TimeoutError",
                    "value": "URL con información privada",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "C:\\private\\server.py",
                                "function": "handle",
                                "lineno": 42,
                                "vars": {"question": "texto privado"},
                            }
                        ]
                    },
                }
            ]
        },
    }

    sanitized = scrub_sentry_event(event, {})

    assert sanitized == {
        "event_id": "id",
        "level": "error",
        "exception": {
            "values": [
                {
                    "type": "TimeoutError",
                    "stacktrace": {
                        "frames": [
                            {
                                "function": "handle",
                                "lineno": 42,
                                "filename": "server.py",
                            }
                        ]
                    },
                }
            ]
        },
    }
