"""Canal Telegram de una consulta local, sin persistir identidad o historial."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Callable
from urllib.parse import quote

import httpx


_LOGGER = logging.getLogger(__name__)
_MAX_TELEGRAM_TEXT = 3900


class TelegramDeliveryError(RuntimeError):
    """Error explícito al enviar una respuesta al usuario de Telegram."""


class TelegramUpdateIds:
    """Deduplicación acotada en memoria sin guardar el cuerpo de los mensajes."""

    def __init__(self, maximum: int = 1000) -> None:
        self._maximum = maximum
        self._lock = threading.Lock()
        self._ids: set[int] = set()
        self._order: deque[int] = deque()

    def contains(self, update_id: int) -> bool:
        with self._lock:
            return update_id in self._ids

    def add(self, update_id: int) -> None:
        with self._lock:
            if update_id in self._ids:
                return
            self._ids.add(update_id)
            self._order.append(update_id)
            while len(self._order) > self._maximum:
                self._ids.discard(self._order.popleft())


def telegram_instructions() -> str:
    return (
        "Este canal procesa una consulta a la vez con las guias locales; "
        "no guarda mensajes ni historial. Telegram recibe el mensaje y la "
        "respuesta. No envies contrasenas, codigos MFA, datos personales ni "
        "informacion confidencial. Para aceptar este tratamiento y consultar, "
        "envia /consulta seguido del problema."
    )


def telegram_reply(update_id: int, chat_id: int, text: str, token: str) -> None:
    """Envía un texto de respuesta y reporta errores sin registrar su contenido."""
    api_url = f"https://api.telegram.org/bot{quote(token, safe=':')}/sendMessage"
    try:
        response = httpx.post(
            api_url,
            json={"chat_id": chat_id, "text": text[:_MAX_TELEGRAM_TEXT]},
            timeout=8,
        )
    except httpx.RequestError as exc:
        _LOGGER.warning(
            "Fallo de transporte de Telegram; update_id=%s error_type=%s",
            update_id,
            type(exc).__name__,
        )
        raise TelegramDeliveryError(
            "No se pudo entregar la respuesta por Telegram."
        ) from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    if (
        not 200 <= response.status_code < 300
        or not isinstance(body, dict)
        or body.get("ok") is not True
    ):
        _LOGGER.warning(
            "Telegram rechazo la respuesta; update_id=%s status_code=%s",
            update_id,
            response.status_code,
        )
        raise TelegramDeliveryError(
            "No se pudo entregar la respuesta por Telegram."
        )


def command_response(
    text: str,
    *,
    responder: Callable[[str, str, dict[str, Any] | None], dict[str, Any]],
    user_id: str = "telegram",
) -> str:
    """Devuelve instrucciones o diagnóstico sin conservar la consulta."""
    stripped = text.strip()
    command, _, arguments = stripped.partition(" ")
    command = command.split("@", 1)[0].casefold()
    if command == "/start":
        return telegram_instructions()
    if command != "/consulta":
        return "Usa /start para ver las condiciones y /consulta <problema> para consultar."
    question = arguments.strip()
    if len(question) < 5:
        return "Describe el problema con al menos 5 caracteres: /consulta <problema>."
    if len(question) > 500:
        return "La consulta admite hasta 500 caracteres. Envia una descripcion mas breve."
    result = responder(question, user_id, None)
    answer = str(result["answer"])
    if result.get("needs_approval"):
        answer += (
            "\n\nEste canal no crea tickets ni conserva el historial. "
            "Contacta al equipo de soporte por el canal institucional."
        )
    return answer[:_MAX_TELEGRAM_TEXT]
