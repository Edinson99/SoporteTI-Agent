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


def test_busqueda_no_coincide_con_palabras_parciales():
    assert buscar_conocimiento("La pared necesita pintura") is None


def test_base_conocimiento_incluye_guias_ti_frecuentes():
    casos = {
        "No puedo abrir Outlook": "kb_correo_001",
        "Mi cuenta esta bloqueada": "kb_acceso_cuenta_001",
        "No puedo conectarme a la VPN": "kb_vpn_001",
        "Necesito instalar programa": "kb_software_001",
        "El microfono no funciona": "kb_perifericos_001",
        "Recibi un correo sospechoso con un enlace sospechoso": "kb_seguridad_correo_001",
        "Tengo una pantalla azul": "kb_pantalla_actualizacion_001",
        "La bateria no carga": "kb_bateria_energia_001",
        "Quiero formatear Windows": "kb_formateo_reinstalacion_001",
        "Como hago una copia de seguridad": "kb_respaldo_datos_001",
        "Mi licencia de software expirada": "kb_licencias_activacion_001",
        "Que hace ipconfig en CMD": "kb_cmd_diagnostico_001",
        "Quiero optimizar rendimiento": "kb_optimizacion_equipo_001",
    }

    for pregunta, articulo_esperado in casos.items():
        articulo = buscar_conocimiento(pregunta)
        assert articulo is not None, pregunta
        assert articulo["id"] == articulo_esperado


def test_guias_de_formateo_y_cmd_indican_limites_seguros():
    formateo = buscar_conocimiento("Quiero formatear Windows")
    comandos = buscar_conocimiento("Que hace ipconfig en CMD")

    assert formateo is not None
    assert any("no inicies el proceso por tu cuenta" in paso for paso in formateo["pasos"])
    assert comandos is not None
    assert any("No ejecutes comandos que borren datos" in paso for paso in comandos["pasos"])


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