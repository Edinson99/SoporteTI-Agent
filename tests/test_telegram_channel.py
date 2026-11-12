import httpx
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.telegram_channel import command_response


def _client():
    return TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 8001),
    )


def test_comando_start_informa_privacidad_sin_procesar_consulta():
    result = command_response(
        "/start",
        responder=lambda *_: (_ for _ in ()).throw(AssertionError("no debe ejecutar")),
    )

    assert "no guarda mensajes ni historial" in result
    assert "/consulta" in result


def test_consulta_telegram_usa_el_diagnostico_local_y_no_persiste_historial():
    observed = {}

    def responder(question, user_id, context):
        observed.update(question=question, user_id=user_id, context=context)
        return {"answer": "Prueba los pasos seguros.", "needs_approval": False}

    result = command_response(
        "/consulta No puedo abrir Outlook",
        responder=responder,
    )

    assert result == "Prueba los pasos seguros."
    assert observed == {
        "question": "No puedo abrir Outlook",
        "user_id": "telegram",
        "context": None,
    }


def test_webhook_exige_secreto_y_envia_respuesta_bot_con_deduplicacion(
    monkeypatch,
):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    calls = []

    def post(url, *, json, timeout):
        calls.append((url, json, timeout))
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.telegram_channel.httpx.post", post)
    client = _client()
    body = {
        "update_id": 99001001,
        "message": {
            "chat": {"id": 12345, "type": "private"},
            "text": "/start",
        },
    }

    unauthorized = client.post("/api/telegram/webhook", json=body)
    processed = client.post(
        "/api/telegram/webhook",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    duplicate = client.post(
        "/api/telegram/webhook",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )

    assert unauthorized.status_code == 403
    assert processed.status_code == 200
    assert processed.json() == {"status": "processed"}
    assert duplicate.json() == {"status": "duplicate"}
    assert len(calls) == 1
    assert calls[0][0] == "https://api.telegram.org/bot123:test-token/sendMessage"
    assert calls[0][1]["chat_id"] == 12345
    assert "no guarda mensajes" in calls[0][1]["text"]
    assert "test-secret" not in repr(calls)


def test_webhook_consulta_diagnostico_sin_usar_hermes(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    observed = {}

    def respond(question, user_id, context):
        observed.update(question=question, user_id=user_id, context=context)
        return {
            "answer": "Consulta local.",
            "needs_approval": False,
        }

    monkeypatch.setattr(main_module.agent, "responder", respond)
    monkeypatch.setattr(
        "app.telegram_channel.httpx.post",
        lambda *_args, **_kwargs: httpx.Response(200, json={"ok": True}),
    )
    response = _client().post(
        "/api/telegram/webhook",
        json={
            "update_id": 99001002,
            "message": {
                "chat": {"id": 12345, "type": "private"},
                "text": "/consulta No puedo abrir Outlook",
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )

    assert response.status_code == 200
    assert observed == {
        "question": "No puedo abrir Outlook",
        "user_id": "telegram",
        "context": None,
    }


def test_webhook_solo_admite_chats_privados(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")

    response = _client().post(
        "/api/telegram/webhook",
        json={
            "update_id": 99001003,
            "message": {
                "chat": {"id": -12345, "type": "group"},
                "text": "/start",
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )

    assert response.status_code == 400
