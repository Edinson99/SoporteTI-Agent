"""API HTTP del agente de soporte TI."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.agent import AgenteSoporteTI
from app.hermes_bridge import HermesBridgeError, generar_respuesta
from app.tickets import TicketService


agent = AgenteSoporteTI()
UI_FILE = Path(__file__).parent / "static" / "index.html"
TICKETS_UI_FILE = Path(__file__).parent / "static" / "tickets.html"

app = FastAPI(
    title="SoporteTI-Agent API",
    description="Agente de soporte TI con diagnostico guiado y conocimiento local.",
    version="1.3.3",
)

ticket_service = TicketService()


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


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    user_id: str = Field(..., min_length=3, max_length=50)
    context: dict[str, Any] | None = None


class ChatContext(BaseModel):
    device: str | None = Field(default=None, max_length=80)
    operating_system: str | None = Field(default=None, max_length=80)
    affected_scope: str | None = Field(default=None, max_length=160)
    error_message: str | None = Field(default=None, max_length=300)
    recent_changes: str | None = Field(default=None, max_length=200)


class ChatNetworkChecks(BaseModel):
    gateway_reachable: bool | None = None
    dns_resolution: bool | None = None
    internet_reachable: bool | None = None


class AgentChatContext(ChatContext):
    network_checks: ChatNetworkChecks | None = None


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1500)


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    user_id: str = Field(..., min_length=3, max_length=50)
    context: AgentChatContext | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=10)


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
    assistant_response: str | None = Field(default=None, max_length=1500)


class TicketCreateResponse(BaseModel):
    ticket_number: str
    email_status: Literal["pending", "not_configured", "sent", "failed"]
    status: Literal["open", "resolved"]


class TicketResolutionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


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
    chat_model_status: Literal["used", "not_used_escalation"] | None = None
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


@app.post("/agent/chat", response_model=AgentAskResponse)
def chat_with_hermes(req: AgentChatRequest, request: Request) -> AgentAskResponse:
    """Genera un diagnostico local y lo redacta con el modelo configurado en Hermes."""
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="El chat Hermes solo esta disponible desde este equipo.",
        )

    context = req.context.model_dump(exclude_none=True) if req.context else None
    resultado = agent.responder(req.question, req.user_id, context)
    historial = [mensaje.model_dump() for mensaje in req.history]
    if resultado["needs_approval"]:
        resultado["ticket_request_id"] = uuid4()
        resultado["contact_required"] = True
        resultado["chat_model_status"] = "not_used_escalation"
        return AgentAskResponse(**resultado)

    try:
        resultado["answer"] = generar_respuesta(
            req.question,
            resultado,
            historial,
        )
    except HermesBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    resultado["chat_model_status"] = "used"
    return AgentAskResponse(**resultado)


@app.post("/agent/tickets", response_model=TicketCreateResponse, status_code=201)
def create_support_ticket(req: TicketCreateRequest, request: Request) -> TicketCreateResponse:
    """Crea y notifica un ticket sin guia despues de recibir el contacto."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="La creacion de tickets es solo local.")

    context = req.context.model_dump(exclude_none=True) if req.context else None
    resultado = agent.responder(req.question, req.user_id, context)
    if not resultado["needs_approval"]:
        raise HTTPException(
            status_code=409,
            detail="Hay una guia de conocimiento para esta consulta; no se creo un ticket.",
        )

    ticket = ticket_service.create_ticket(
        request_id=str(req.request_id),
        question=req.question,
        user_id=req.user_id,
        category=resultado["category"],
        priority=resultado["priority"],
        diagnosis=resultado["escalation_reason"] or resultado["diagnosis"]["summary"],
        context=context,
        history=[mensaje.model_dump() for mensaje in req.history],
        contact_name=req.contact.name,
        contact_email=req.contact.email,
        contact_phone=req.contact.phone,
        assistant_response=req.assistant_response,
    )
    return TicketCreateResponse(
        ticket_number=ticket["incident_id"],
        email_status=ticket["ticket_email_status"],
        status=ticket["status"],
    )


@app.get("/api/tickets")
def list_support_tickets(request: Request) -> list[dict[str, Any]]:
    """Lista casos en el panel tecnico local."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    return ticket_service.list_tickets()


@app.post("/api/tickets/{ticket_number}/resolve")
def resolve_support_ticket(
    ticket_number: str,
    req: TicketResolutionRequest,
    request: Request,
) -> dict[str, str]:
    """Guarda el cierre y la nota del tecnico."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="El panel solo esta disponible localmente.")
    ticket = ticket_service.resolve_ticket(ticket_number, req.note.strip())
    if ticket is None:
        raise HTTPException(status_code=404, detail="No existe ese ticket.")
    return ticket