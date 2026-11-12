"""API HTTP del agente de soporte TI."""

from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent import AgenteSoporteTI
from app.dataconnect_tickets import DataConnectError, FirebaseDataConnectTicketService
from app.feedback import (
    FeedbackStoreError,
    LocalFeedbackStore,
)
from app.hermes_bridge import (
    HermesBridgeError,
    generar_respuesta,
    normalizar_respuesta,
)
from app.observability import (
    RequestTelemetry,
    SlidingWindowRateLimiter,
    configure_sentry,
    rate_limit_from_environment,
)
from app.tickets import TicketService
from app.telegram_channel import (
    TelegramDeliveryError,
    TelegramUpdateIds,
    command_response,
    telegram_reply,
)
from app.tools import cargar_base_conocimiento


agent = AgenteSoporteTI()
UI_FILE = Path(__file__).parent / "static" / "index.html"
TICKETS_UI_FILE = Path(__file__).parent / "static" / "tickets.html"
STATUS_UI_FILE = Path(__file__).parent / "static" / "status.html"
_IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_CHAT_HISTORY_MESSAGE_LENGTH = 4000
_telegram_updates = TelegramUpdateIds()
_sentry_enabled = configure_sentry()

app = FastAPI(
    title="SoporteTI-Agent API",
    description="Agente de soporte TI con diagnostico guiado y conocimiento local.",
    version="1.4.0",
)
_telemetry = RequestTelemetry()
_rate_limiter = SlidingWindowRateLimiter(limit=rate_limit_from_environment())

def _feedback_store() -> LocalFeedbackStore:
    return LocalFeedbackStore()


def _create_ticket_service() -> TicketService | FirebaseDataConnectTicketService:
    backend = os.getenv("SOPORTE_TICKETS_BACKEND", "sqlite").strip().casefold()
    if backend == "sqlite":
        return TicketService()
    if backend == "firebase":
        return FirebaseDataConnectTicketService()
    raise RuntimeError(
        "SOPORTE_TICKETS_BACKEND debe ser 'sqlite' o 'firebase'."
    )


ticket_service = _create_ticket_service()


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    started = time.monotonic()
    route_limit = {
        "/agent/ask",
        "/agent/chat",
        "/agent/tickets",
        "/api/feedback",
        "/api/telegram/webhook",
    }
    route_name = request.scope.get("route")
    route = getattr(route_name, "path", "unmatched")
    method = request.method.upper()
    client_host = request.client.host if request.client else "unknown"
    limited_route = request.url.path if request.url.path in route_limit else None
    if limited_route and not _rate_limiter.allow(client_host, limited_route):
        response = JSONResponse(
            status_code=429,
            content={"detail": "Se alcanzo el limite temporal de solicitudes."},
            headers={"Retry-After": "60"},
        )
        _telemetry.record(
            method,
            limited_route,
            response.status_code,
            time.monotonic() - started,
        )
        return response
    try:
        response = await call_next(request)
    except Exception:
        route_name = request.scope.get("route")
        route = getattr(route_name, "path", "unmatched")
        _telemetry.record(method, route, 500, time.monotonic() - started)
        raise
    route_name = request.scope.get("route")
    route = getattr(route_name, "path", "unmatched")
    _telemetry.record(method, route, response.status_code, time.monotonic() - started)
    return response


@app.get("/", include_in_schema=False)
def web_interface() -> FileResponse:
    """Sirve la interfaz gráfica del agente."""
    return FileResponse(UI_FILE)


@app.get("/tickets", include_in_schema=False)
def tickets_interface(request: Request) -> FileResponse:
    """Sirve el panel tecnico solo a clientes locales."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    return FileResponse(TICKETS_UI_FILE)


@app.get("/status", include_in_schema=False)
def status_interface() -> FileResponse:
    """Sirve la pagina publica y minima del estado de la API."""
    return FileResponse(STATUS_UI_FILE)


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    user_id: str = Field(..., min_length=3, max_length=50)
    context: dict[str, Any] | None = None


class ChatContext(BaseModel):
    device: str | None = Field(default=None, max_length=80)
    operating_system: str | None = Field(default=None, max_length=80)
    affected_scope: str | None = Field(default=None, max_length=160)
    error_message: str | None = Field(default=None, max_length=1000)
    recent_changes: str | None = Field(default=None, max_length=200)


class ChatNetworkChecks(BaseModel):
    gateway_reachable: bool | None = None
    dns_resolution: bool | None = None
    internet_reachable: bool | None = None


class AgentChatContext(ChatContext):
    network_checks: ChatNetworkChecks | None = None


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        ..., min_length=1, max_length=_MAX_CHAT_HISTORY_MESSAGE_LENGTH
    )


class ChatImage(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=120)
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    data_url: str = Field(..., min_length=40, max_length=2_800_000)

    @field_validator("file_name")
    @classmethod
    def sanitize_file_name(cls, value: str) -> str:
        name = value.replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(character for character in name if character.isprintable())
        if not name or name in {".", ".."}:
            raise ValueError("El nombre de la imagen no es válido.")
        return name[:120]

    @model_validator(mode="after")
    def validate_image_data(self) -> "ChatImage":
        prefix = f"data:{self.content_type};base64,"
        if not self.data_url.startswith(prefix):
            raise ValueError("El formato de la imagen no coincide con su contenido.")
        try:
            image_data = base64.b64decode(
                self.data_url[len(prefix):],
                validate=True,
            )
        except binascii.Error as exc:
            raise ValueError("La imagen está codificada de forma inválida.") from exc
        if not image_data or len(image_data) > 2 * 1024 * 1024:
            raise ValueError("Cada imagen debe pesar como máximo 2 MiB.")
        signatures = {
            "image/jpeg": image_data.startswith(b"\xff\xd8\xff"),
            "image/png": image_data.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": (
                len(image_data) >= 12
                and image_data[:4] == b"RIFF"
                and image_data[8:12] == b"WEBP"
            ),
        }
        if not signatures[self.content_type]:
            raise ValueError("El archivo no contiene una imagen compatible.")
        return self

    def decoded(self) -> bytes:
        return base64.b64decode(self.data_url.split(",", 1)[1])


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    user_id: str = Field(..., min_length=3, max_length=50)
    context: AgentChatContext | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=10)
    attachments: list[ChatImage] = Field(default_factory=list, max_length=3)


class TicketContact(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(
        ...,
        min_length=6,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    phone: str = Field(
        ...,
        min_length=7,
        max_length=30,
        pattern=r"^[+0-9().\-\s]+$",
    )

    @field_validator("phone")
    @classmethod
    def phone_has_valid_digit_count(cls, value: str) -> str:
        digit_count = sum(character.isdigit() for character in value)
        if not 7 <= digit_count <= 15:
            raise ValueError("El telefono debe contener entre 7 y 15 digitos.")
        return value


class TicketCreateRequest(AgentChatRequest):
    request_id: UUID
    contact: TicketContact
    consent_to_email: bool
    assistant_response: str | None = Field(default=None, max_length=1500)


class TicketCreateResponse(BaseModel):
    ticket_number: str
    email_status: Literal["pending", "not_configured", "sent", "failed"]
    status: Literal["open", "resolved"]
    email_provider: Literal["gmail", "resend", "none"] = "none"
    email_failure_class: Literal[
        "pending",
        "none",
        "not_configured",
        "configuration",
        "transient",
    ] = "not_configured"
    alert_status: Literal["pending", "not_configured", "sent", "failed", "skipped"] = "skipped"


class TicketResolutionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class FeedbackRequest(BaseModel):
    article_id: str = Field(..., min_length=3, max_length=80)
    rating: Literal["useful", "not_useful"]

    @field_validator("article_id")
    @classmethod
    def validate_article_id(cls, value: str) -> str:
        article_ids = {
            articulo["id"] for articulo in cargar_base_conocimiento()
        }
        if value not in article_ids:
            raise ValueError("La guia valorada no existe en la base local.")
        return value


class TelegramChat(BaseModel):
    id: int
    type: Literal["private"]


class TelegramMessage(BaseModel):
    chat: TelegramChat
    text: str | None = Field(default=None, max_length=4000)


class TelegramUpdate(BaseModel):
    update_id: int = Field(..., ge=0)
    message: TelegramMessage | None = None


class FeedbackResponse(BaseModel):
    status: Literal["recorded"]


class FeedbackSummaryItem(BaseModel):
    article_id: str
    useful: int
    not_useful: int
    total: int


class DiagnosticHypothesis(BaseModel):
    cause: str
    confidence: float = Field(..., ge=0, le=1)
    sources: list[str]
    rationale: str
    tests: list[str]


class AgentDiagnosis(BaseModel):
    summary: str
    hypotheses: list[DiagnosticHypothesis]
    tests: list[str]


class AgentAskResponse(BaseModel):
    answer: str
    sources: list[str]
    needs_approval: bool
    next_action: str
    incident_id: str | None = None
    ticket_email_status: Literal["not_configured", "sent", "failed"] | None = None
    ticket_request_id: UUID | None = None
    contact_required: bool = False
    chat_model_status: Literal["used"] | None = None
    category: Literal[
        "redes",
        "cuentas",
        "ciberseguridad",
        "hardware",
        "sistemas_operativos",
        "correo",
        "software",
        "datos",
        "diagnostico",
        "general",
    ]
    priority: Literal["normal", "high"]
    diagnosis: AgentDiagnosis
    evidence: list[str]
    confidence: float = Field(..., ge=0, le=1)
    recommended_actions: list[str]
    escalation_reason: str | None = None
    follow_up_questions: list[str]


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    """Devuelve errores de contrato como JSON legible con estado 400."""
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder({"detail": "Solicitud invalida.", "errors": exc.errors()}),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Comprueba que la API puede atender solicitudes."""
    return {"status": "ok"}


@app.get("/api/status")
def service_status() -> dict[str, Any]:
    """Expone estado y configuración general sin sondear ni filtrar secretos."""
    backend = os.getenv("SOPORTE_TICKETS_BACKEND", "sqlite").strip().casefold()
    semantic_setting = os.getenv(
        "SOPORTE_SEMANTIC_SEARCH", "false"
    ).strip().casefold()
    semantic_status = (
        "enabled"
        if semantic_setting == "true"
        else "disabled"
        if semantic_setting == "false"
        else "misconfigured"
    )
    gmail_sender = os.getenv("GMAIL_SENDER", "").strip()
    gmail_recipient = os.getenv("GMAIL_TO_EMAIL", "").strip()
    token_file = Path(
        os.getenv("GMAIL_OAUTH_TOKEN_FILE", ".secrets/gmail-token.json")
    )
    if not token_file.is_absolute():
        token_file = Path(__file__).resolve().parent.parent / token_file
    email_configured = (
        all(
            os.getenv(name, "").strip()
            for name in ("RESEND_API_KEY", "RESEND_FROM", "RESEND_TO_EMAIL")
        )
        or (
            bool(gmail_sender)
            and bool(gmail_recipient)
            and token_file.is_file()
        )
    )
    telegram_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    telegram_url = (
        f"https://t.me/{telegram_username}"
        if re.fullmatch(r"[A-Za-z0-9_]{5,32}", telegram_username)
        else None
    )
    telegram_configured = (
        bool(
            os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            and os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        )
        or all(
            os.getenv(name, "").strip()
            for name in (
                "TELEGRAM_MTPROTO_API_ID",
                "TELEGRAM_MTPROTO_API_HASH",
                "TELEGRAM_MTPROTO_ALLOWED_USER_IDS",
            )
        )
    )
    overall_status = (
        "degraded"
        if backend not in {"sqlite", "firebase"} or semantic_status == "misconfigured"
        else "operational"
    )
    return {
        "status": overall_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "stale_after_seconds": 60,
        "components": {
            "api": "operational",
            "ticket_store": (
                "configured"
                if backend in {"sqlite", "firebase"}
                else "misconfigured"
            ),
            "semantic_search": semantic_status,
            "error_monitoring": "enabled" if _sentry_enabled else "disabled",
            "email": "configured" if email_configured else "not_configured",
            "alerts": (
                "configured"
                if os.getenv("SLACK_WEBHOOK_URL", "").strip()
                else "not_configured"
            ),
            "telegram": "configured" if telegram_configured else "not_configured",
        },
        "telegram_url": telegram_url,
    }


@app.get("/api/metrics")
def service_metrics(request: Request) -> dict[str, Any]:
    """Devuelve métricas agregadas solo a clientes locales."""
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="Las metricas operativas solo estan disponibles localmente.",
        )
    return _telemetry.snapshot()


@app.post("/api/telegram/webhook")
def telegram_webhook(
    update: TelegramUpdate,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Procesa /start o una consulta puntual; no persiste chat ni identidad."""
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not webhook_secret or not bot_token:
        raise HTTPException(
            status_code=503,
            detail="El canal de Telegram no esta configurado.",
        )
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        webhook_secret,
        x_telegram_bot_api_secret_token,
    ):
        raise HTTPException(status_code=403, detail="Webhook no autorizado.")
    if _telegram_updates.contains(update.update_id):
        return {"status": "duplicate"}
    if update.message is None:
        _telegram_updates.add(update.update_id)
        return {"status": "ignored"}
    message = update.message
    text = message.text or ""
    response_text = command_response(
        text,
        responder=agent.responder,
    )
    try:
        telegram_reply(
            update.update_id,
            message.chat.id,
            response_text,
            bot_token,
        )
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _telegram_updates.add(update.update_id)
    return {"status": "processed"}


@app.post("/api/feedback", response_model=FeedbackResponse)
def record_feedback(
    req: FeedbackRequest,
    request: Request,
) -> FeedbackResponse:
    """Guarda una valoracion local sin asociarla a la conversacion o usuario."""
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="El feedback solo esta disponible localmente.",
        )
    try:
        _feedback_store().record(req.article_id, req.rating)
    except FeedbackStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FeedbackResponse(status="recorded")


@app.get("/api/feedback/summary", response_model=list[FeedbackSummaryItem])
def feedback_summary(request: Request) -> list[FeedbackSummaryItem]:
    """Devuelve conteos locales por guia, sin eventos individuales."""
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="El resumen de feedback solo esta disponible localmente.",
        )
    try:
        return [
            FeedbackSummaryItem(**item)
            for item in _feedback_store().summary()
        ]
    except FeedbackStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/agent/ask", response_model=AgentAskResponse)
def ask_agent(req: AgentAskRequest) -> AgentAskResponse:
    """Valida el problema, consulta conocimiento local y devuelve una respuesta segura."""
    resultado = agent.responder(req.question, req.user_id, req.context)
    if resultado["needs_approval"]:
        resultado["ticket_request_id"] = uuid4()
        resultado["contact_required"] = True
    return AgentAskResponse(**resultado)



def _is_loopback_request(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            return False
    except ValueError:
        return False

    host = request.url.hostname
    if host == "localhost":
        return True
    try:
        return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def _requests_technician(question: str, history: list[dict[str, str]]) -> bool:
    normalized = question.casefold()
    direct_request = re.search(
        r"\b(contactar|contacto|crear (?:un )?ticket|hablar con|"
        r"solicitar soporte|escalar|tecnic[oa]|persona de soporte)\b",
        normalized,
    )
    if direct_request:
        return True
    if history and history[-1]["role"] == "assistant":
        assistant_asked = re.search(
            r"\b(tecnic[oa]|contactar|crear un ticket|soporte humano)\b",
            history[-1]["content"].casefold(),
        )
        affirmative = re.match(
            r"^\s*(si|sí|por favor|de acuerdo|claro|quiero)\b",
            normalized,
        )
        return bool(assistant_asked and affirmative)
    return False


def _ensure_chat_follow_up(
    answer: str,
    follow_up_questions: list[str],
    recommended_actions: list[str],
) -> str:
    if answer.rstrip().endswith("?"):
        return answer
    question = (
        follow_up_questions[0]
        if follow_up_questions
        else (
            "¿Pudiste probar alguno de los pasos recomendados y qué resultado obtuviste?"
            if recommended_actions
            else "¿Qué ocurre exactamente cuando intentas usarlo y qué mensaje aparece?"
        )
    )
    return f"{answer.rstrip()}\n\nPara continuar: {question}"


@app.post("/agent/chat", response_model=AgentAskResponse)
def chat_with_hermes(req: AgentChatRequest, request: Request) -> AgentAskResponse:
    """Genera un diagnostico local y lo redacta con el modelo configurado en Hermes."""
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="El chat Hermes solo esta disponible desde este equipo.",
        )

    context = req.context.model_dump(exclude_none=True) if req.context else None
    historial = [mensaje.model_dump() for mensaje in req.history]
    prior_user_messages = [
        mensaje["content"]
        for mensaje in historial
        if mensaje["role"] == "user"
    ][-3:]
    diagnostic_question = " ".join([*prior_user_messages, req.question])
    resultado = agent.responder(diagnostic_question, req.user_id, context)
    user_turn_count = len(prior_user_messages) + 1
    explicit_contact_request = _requests_technician(req.question, historial)
    result_needs_approval = resultado["needs_approval"]
    resultado["contact_required"] = (
        user_turn_count >= 4 or explicit_contact_request
    )
    if result_needs_approval and not resultado["contact_required"] and not resultado["follow_up_questions"]:
        resultado["follow_up_questions"] = [
            "¿Qué paso intentaste hasta ahora y qué resultado obtuviste?"
        ]
    try:
        with tempfile.TemporaryDirectory(prefix="soporteti-chat-") as directory:
            image_paths = []
            for attachment in req.attachments:
                image_path = Path(directory) / (
                    f"{uuid4()}{_IMAGE_EXTENSIONS[attachment.content_type]}"
                )
                image_path.write_bytes(attachment.decoded())
                image_paths.append(image_path)
            if image_paths:
                resultado["answer"] = generar_respuesta(
                    req.question,
                    resultado,
                    historial,
                    image_paths=image_paths,
                )
            else:
                resultado["answer"] = generar_respuesta(
                    req.question,
                    resultado,
                    historial,
                )
    except HermesBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not resultado["contact_required"]:
        resultado["answer"] = _ensure_chat_follow_up(
            resultado["answer"],
            resultado["follow_up_questions"],
            resultado["recommended_actions"],
        )
    resultado["answer"] = normalizar_respuesta(resultado["answer"])
    resultado["chat_model_status"] = "used"
    if resultado["contact_required"]:
        resultado["ticket_request_id"] = uuid4()
    return AgentAskResponse(**resultado)


@app.post("/agent/tickets", response_model=TicketCreateResponse, status_code=201)
def create_support_ticket(req: TicketCreateRequest, request: Request) -> TicketCreateResponse:
    """Crea un ticket consentido cuando el chat no resuelve la incidencia."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="La creacion de tickets es solo local.")
    if not req.consent_to_email:
        raise HTTPException(
            status_code=403,
            detail="Se requiere consentimiento para compartir el caso con el técnico.",
        )

    context = req.context.model_dump(exclude_none=True) if req.context else None
    historial = [mensaje.model_dump() for mensaje in req.history]
    prior_user_messages = [
        mensaje["content"]
        for mensaje in historial
        if mensaje["role"] == "user"
    ][-3:]
    resultado = agent.responder(
        " ".join([*prior_user_messages, req.question]),
        req.user_id,
        context,
    )
    contact_turn_count = len(prior_user_messages) + 1
    explicit_contact_request = _requests_technician(req.question, historial)
    if not (
        resultado["needs_approval"]
        or contact_turn_count >= 4
        or explicit_contact_request
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Continúa el autodiagnóstico o solicita contactar al técnico "
                "antes de crear el ticket."
            ),
        )

    try:
        ticket = ticket_service.create_ticket(
            request_id=str(req.request_id),
            question=req.question,
            user_id=req.user_id,
            category=resultado["category"],
            priority=resultado["priority"],
            diagnosis=(
                resultado["escalation_reason"]
                or (
                    resultado["diagnosis"]["summary"]
                    if resultado["needs_approval"]
                    else "El usuario solicita revisión técnica tras el autodiagnóstico."
                )
            ),
            context=context,
            history=[mensaje.model_dump() for mensaje in req.history],
            contact_name=req.contact.name,
            contact_email=req.contact.email,
            contact_phone=req.contact.phone,
            assistant_response=req.assistant_response,
            attachments=[
                {
                    "id": str(uuid4()),
                    "file_name": attachment.file_name,
                    "content_type": attachment.content_type,
                    "data": attachment.decoded(),
                }
                for attachment in req.attachments
            ],
        )
    except DataConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible guardar el ticket en Firebase Data Connect: {exc}",
        ) from exc
    return TicketCreateResponse(
        ticket_number=ticket["incident_id"],
        email_status=ticket["ticket_email_status"],
        status=ticket["status"],
        email_provider=ticket.get("email_provider", "none"),
        email_failure_class=ticket.get("email_failure_class", "not_configured"),
        alert_status=ticket.get("alert_status", "skipped"),
    )


@app.get("/api/tickets")
def list_support_tickets(request: Request) -> list[dict[str, Any]]:
    """Lista casos en el panel tecnico local."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    try:
        return ticket_service.list_tickets()
    except DataConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar Firebase Data Connect: {exc}",
        ) from exc


@app.post("/api/tickets/{ticket_number}/resolve")
def resolve_support_ticket(
    ticket_number: str,
    req: TicketResolutionRequest,
    request: Request,
) -> dict[str, str]:
    """Guarda el cierre y la nota del tecnico."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    try:
        ticket = ticket_service.resolve_ticket(ticket_number, req.note.strip())
    except DataConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible actualizar Firebase Data Connect: {exc}",
        ) from exc
    if ticket is None:
        raise HTTPException(status_code=404, detail="No existe ese ticket.")
    return ticket


@app.get("/api/tickets/{ticket_number}/attachments/{attachment_id}")
def get_ticket_attachment(
    ticket_number: str,
    attachment_id: UUID,
    request: Request,
) -> Response:
    """Entrega una imagen adjunta a un ticket solo a clientes locales."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    try:
        attachment = ticket_service.get_attachment(ticket_number, str(attachment_id))
    except DataConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No fue posible consultar el adjunto en Firebase Data Connect: {exc}",
        ) from exc
    if attachment is None:
        raise HTTPException(status_code=404, detail="No existe ese adjunto.")
    return Response(
        content=attachment["data"],
        media_type=attachment["content_type"],
        headers={"Content-Disposition": "inline"},
    )