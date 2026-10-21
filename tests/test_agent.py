"""Pruebas del flujo objetivo -> herramientas -> resultado -> limites."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent import AgenteSoporteTI
from app.main import app
from app.mcp_server import consultar_soporte_ti
from app.tools import buscar_conocimiento

client = TestClient(app)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_ejemplos_json_son_validos_y_contienen_el_contrato():
    request = json.loads((DATA_DIR / "agent_request.json").read_text(encoding="utf-8"))
    response = json.loads((DATA_DIR / "agent_response.json").read_text(encoding="utf-8"))
    assert {"question", "user_id", "context"} <= request.keys()
    assert {"answer", "sources", "needs_approval", "next_action"} <= response.keys()
    assert isinstance(response["sources"], list)
    assert isinstance(response["needs_approval"], bool)


def test_busca_conocimiento_de_internet():
    articulo = buscar_conocimiento("No tengo internet en mi portatil")
    assert articulo is not None
    assert articulo["id"] == "kb_internet_001"


def test_agente_recomienda_pasos_seguros_para_caso_conocido():
    resultado = AgenteSoporteTI().responder("La impresora no imprime", "USR-1042")
    assert resultado["sources"] == ["kb_impresora_001"]
    assert resultado["needs_approval"] is False
    assert resultado["next_action"] == "seguir_pasos_seguros"


def test_agente_escala_caso_sin_guia():
    resultado = AgenteSoporteTI().responder("La cafetera no funciona", "USR-1042")
    assert resultado["sources"] == ["protocolo_escalamiento"]
    assert resultado["needs_approval"] is True
    assert resultado["next_action"] == "borrador_pendiente_aprobacion"


def test_health():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_agent_ask_retorna_diagnostico_ti():
    respuesta = client.post(
        "/agent/ask",
        json={
            "question": "No tengo internet en mi portatil",
            "user_id": "USR-1042",
            "context": {"device": "portatil", "operating_system": "Windows 11"},
        },
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["sources"] == ["kb_internet_001"]
    assert datos["needs_approval"] is False


def test_agent_ask_rechaza_question_faltante():
    respuesta = client.post("/agent/ask", json={"user_id": "USR-1042"})
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Solicitud invalida."


def test_herramienta_mcp_consulta_el_diagnostico_compartido():
    resultado = consultar_soporte_ti(
        "No tengo internet en mi portatil",
        "USR-1042",
        {"device": "portatil"},
    )

    assert resultado["sources"] == ["kb_internet_001"]
    assert resultado["needs_approval"] is False
    assert resultado["next_action"] == "seguir_pasos_seguros"


def test_herramienta_mcp_escala_casos_sin_guia():
    resultado = consultar_soporte_ti("La cafetera no funciona", "USR-1042")

    assert resultado["sources"] == ["protocolo_escalamiento"]
    assert resultado["needs_approval"] is True
    assert resultado["next_action"] == "borrador_pendiente_aprobacion"