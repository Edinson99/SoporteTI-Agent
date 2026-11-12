import asyncio

import pytest

from scripts.telegram_mtproto import (
    is_authorized_private_sender,
    load_settings,
    parse_allowed_user_ids,
    process_private_message,
)


def test_parse_allowed_user_ids_returns_unique_positive_ids() -> None:
    assert parse_allowed_user_ids("123, 456,123") == frozenset({123, 456})


@pytest.mark.parametrize("value", ["", " , ", "abc,123", "-123", "0"])
def test_parse_allowed_user_ids_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_allowed_user_ids(value)


def test_authorization_requires_private_chat_and_allowlisted_sender() -> None:
    allowed = frozenset({123})
    assert is_authorized_private_sender(
        123,
        is_private=True,
        allowed_user_ids=allowed,
    )
    assert not is_authorized_private_sender(
        456,
        is_private=True,
        allowed_user_ids=allowed,
    )
    assert not is_authorized_private_sender(
        123,
        is_private=False,
        allowed_user_ids=allowed,
    )


def test_message_handler_answers_only_allowlisted_private_commands() -> None:
    class FakeEvent:
        def __init__(self, sender_id: int, is_private: bool, raw_text: str) -> None:
            self.sender_id = sender_id
            self.is_private = is_private
            self.raw_text = raw_text
            self.replies: list[str] = []

        async def respond(self, message: str) -> None:
            self.replies.append(message)

    responder_calls: list[str] = []

    def responder(question: str, user_id: str, context: dict | None) -> dict:
        responder_calls.append(question)
        return {"answer": "Respuesta local", "needs_approval": False}

    allowed_event = FakeEvent(123, True, "/consulta no funciona internet")
    unauthorized_event = FakeEvent(456, True, "/start")
    group_event = FakeEvent(123, False, "/start")
    other_message = FakeEvent(123, True, "hola")

    assert asyncio.run(
        process_private_message(
            allowed_event,
            allowed_user_ids=frozenset({123}),
            responder=responder,
        )
    )
    assert not asyncio.run(
        process_private_message(
            unauthorized_event,
            allowed_user_ids=frozenset({123}),
            responder=responder,
        )
    )
    assert not asyncio.run(
        process_private_message(
            group_event,
            allowed_user_ids=frozenset({123}),
            responder=responder,
        )
    )
    assert not asyncio.run(
        process_private_message(
            other_message,
            allowed_user_ids=frozenset({123}),
            responder=responder,
        )
    )
    assert allowed_event.replies == ["Respuesta local"]
    assert unauthorized_event.replies == []
    assert group_event.replies == []
    assert other_message.replies == []
    assert responder_calls == ["no funciona internet"]


def test_load_settings_requires_all_credentials_and_allowlist() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_MTPROTO_API_ID"):
        load_settings({})


def test_load_settings_uses_private_local_session_directory() -> None:
    settings = load_settings(
        {
            "TELEGRAM_MTPROTO_API_ID": "12345",
            "TELEGRAM_MTPROTO_API_HASH": "a" * 32,
            "TELEGRAM_MTPROTO_ALLOWED_USER_IDS": "123,456",
        }
    )
    assert settings.allowed_user_ids == frozenset({123, 456})
    assert settings.session_base_path.name == "telegram-mtproto"
    assert settings.session_base_path.parent.name == ".secrets"


def test_load_settings_rejects_malformed_api_hash() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_MTPROTO_API_HASH"):
        load_settings(
            {
                "TELEGRAM_MTPROTO_API_ID": "12345",
                "TELEGRAM_MTPROTO_API_HASH": "not-a-hash",
                "TELEGRAM_MTPROTO_ALLOWED_USER_IDS": "123",
            }
        )
