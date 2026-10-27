"""API HTTP del agente de soporte TI."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.agent import AgenteSoporteTI
from app.hermes_bridge import HermesBridgeError, generar_respuesta


agent = AgenteSoporteTI()
UI_FILE = Path(__file__).parent / "static" / "index.html"

app = FastAPI(
    title="SoporteTI-Agent API",
    description="Agente de soporte TI con diagnostico guiado y conocimiento local.",
    version="1.3.0",
)


@app.get("/", include_in_schema=False)
def web_interface() -> FileResponse:
    """Sirve la interfaz gráfica del agente."""
    return FileResponse(UI_FILE)


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
    return AgentAskResponse(**agent.responder(req.question, req.user_id, req.context))


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
    try:
        resultado["answer"] = generar_respuesta(
            req.question,
            resultado,
            historial,
        )
    except HermesBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AgentAskResponse(**resultado)