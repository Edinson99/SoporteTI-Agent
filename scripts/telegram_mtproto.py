"""Run the optional, allowlisted Telegram MTProto personal-account channel."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Protocol

from dotenv import load_dotenv

from app.agent import AgenteSoporteTI
from app.telegram_channel import command_response


_LOGGER = logging.getLogger("telegram_mtproto")
_API_HASH_PATTERN = re.compile(r"[0-9a-fA-F]{32}\Z")


@dataclass(frozen=True)
class TelegramMTProtoSettings:
    api_id: int
    api_hash: str
    allowed_user_ids: frozenset[int]
    session_base_path: Path


class TelegramIncomingEvent(Protocol):
    sender_id: int | None
    is_private: bool
    raw_text: str

    def respond(self, message: str) -> Awaitable[Any]: ...


def parse_allowed_user_ids(value: str) -> frozenset[int]:
    """Parse a comma-separated allowlist of positive Telegram user IDs."""
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries:
        raise ValueError("Configura TELEGRAM_MTPROTO_ALLOWED_USER_IDS.")
    if any(not entry.isascii() or not entry.isdecimal() for entry in entries):
        raise ValueError("Los IDs permitidos de Telegram deben ser enteros positivos.")
    user_ids = frozenset(int(entry) for entry in entries)
    if any(user_id <= 0 for user_id in user_ids):
        raise ValueError("Los IDs permitidos de Telegram deben ser enteros positivos.")
    return user_ids


def is_authorized_private_sender(
    sender_id: int | None,
    *,
    is_private: bool,
    allowed_user_ids: frozenset[int],
) -> bool:
    return (
        is_private
        and sender_id is not None
        and sender_id in allowed_user_ids
    )


def load_settings(
    environ: Mapping[str, str] | None = None,
) -> TelegramMTProtoSettings:
    """Load required credentials without logging or persisting their values."""
    env = os.environ if environ is None else environ
    raw_api_id = env.get("TELEGRAM_MTPROTO_API_ID", "").strip()
    api_hash = env.get("TELEGRAM_MTPROTO_API_HASH", "").strip()
    if not raw_api_id.isascii() or not raw_api_id.isdecimal():
        raise ValueError("Configura TELEGRAM_MTPROTO_API_ID con un entero positivo.")
    api_id = int(raw_api_id)
    if api_id <= 0:
        raise ValueError("Configura TELEGRAM_MTPROTO_API_ID con un entero positivo.")
    if not _API_HASH_PATTERN.fullmatch(api_hash):
        raise ValueError("Configura TELEGRAM_MTPROTO_API_HASH con el formato esperado.")
    allowed_user_ids = parse_allowed_user_ids(
        env.get("TELEGRAM_MTPROTO_ALLOWED_USER_IDS", "")
    )
    project_root = Path(__file__).resolve().parents[1]
    session_directory = project_root / ".secrets"
    return TelegramMTProtoSettings(
        api_id=api_id,
        api_hash=api_hash,
        allowed_user_ids=allowed_user_ids,
        session_base_path=session_directory / "telegram-mtproto",
    )


async def process_private_message(
    event: TelegramIncomingEvent,
    *,
    allowed_user_ids: frozenset[int],
    responder: Callable[[str, str, dict[str, Any] | None], dict[str, Any]],
) -> bool:
    """Reply only to supported commands from allowlisted private senders."""
    if not is_authorized_private_sender(
        event.sender_id,
        is_private=event.is_private,
        allowed_user_ids=allowed_user_ids,
    ):
        return False
    message = event.raw_text or ""
    command = message.strip().partition(" ")[0].split("@", 1)[0].casefold()
    if command not in {"/start", "/consulta"}:
        return False
    response_text = command_response(message, responder=responder)
    await event.respond(response_text)
    return True


async def run_client(settings: TelegramMTProtoSettings) -> None:
    """Connect the personal account and handle only allowlisted commands."""
    from telethon import TelegramClient, events
    from telethon.errors import RPCError

    settings.session_base_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    client = TelegramClient(
        str(settings.session_base_path),
        settings.api_id,
        settings.api_hash,
    )
    agent = AgenteSoporteTI()

    @client.on(events.NewMessage(incoming=True))
    async def handle_private_command(event) -> None:
        try:
            await process_private_message(
                event,
                allowed_user_ids=settings.allowed_user_ids,
                responder=agent.responder,
            )
        except RPCError as exc:
            _LOGGER.warning(
                "No se pudo entregar respuesta MTProto; error_type=%s",
                type(exc).__name__,
            )
            raise

    await client.start()
    _LOGGER.info("Canal MTProto conectado; acceso restringido por allowlist.")
    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    try:
        settings = load_settings()
    except ValueError as exc:
        raise SystemExit(f"Configuracion MTProto invalida: {exc}") from exc
    asyncio.run(run_client(settings))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
