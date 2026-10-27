"""Pruebas del flujo objetivo -> herramientas -> resultado -> limites."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.hermes_bridge as hermes_bridge
from app.agent import AgenteSoporteTI
from app.lambda_handler import handler as lambda_handler
from app.main import AgentAskResponse, app
from app.mcp_server import consultar_soporte_ti
from app.tools import buscar_conocimiento, buscar_conocimientos, cargar_base_conocimiento

client = TestClient(
    app,
    base_url="http://127.0.0.1",
    client=("127.0.0.1", 8001),
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_ejemplos_json_son_validos_y_contienen_el_contrato():
    request = json.loads((DATA_DIR / "agent_request.json").read_text(encoding="utf-8"))
    response = json.loads((DATA_DIR / "agent_response.json").read_text(encoding="utf-8"))
    assert {"question", "user_id", "context"} <= request.keys()
    assert {
        "answer",
        "sources",
        "needs_approval",
        "next_action",
        "incident_id",
        "category",
        "priority",
        "diagnosis",
        "evidence",
        "confidence",
        "recommended_actions",
        "escalation_reason",
        "follow_up_questions",
    } <= response.keys()
    assert isinstance(response["sources"], list)
    assert isinstance(response["needs_approval"], bool)
    AgentAskResponse.model_validate(response)


def test_busca_conocimiento_de_internet():
    articulo = buscar_conocimiento("No tengo internet en mi portatil")
    assert articulo is not None
    assert articulo["id"] == "kb_internet_001"


def test_busqueda_no_coincide_con_palabras_parciales():
    assert buscar_conocimiento("La pared necesita pintura") is None


def test_busqueda_normaliza_acentos_y_devuelve_varias_coincidencias():
    assert buscar_conocimiento("Tengo una licéncia expirada")["id"] == "kb_licencias_activacion_001"

    resultados = buscar_conocimientos("No funciona el wifi y la impresora")
    fuentes = {resultado["articulo"]["id"] for resultado in resultados}
    assert {"kb_internet_001", "kb_impresora_001"} <= fuentes


def test_base_de_conocimiento_se_carga_una_vez():
    cargar_base_conocimiento.cache_clear()
    buscar_conocimiento("internet")
    buscar_conocimiento("wifi")
    assert cargar_base_conocimiento.cache_info().misses == 1
    assert cargar_base_conocimiento.cache_info().hits == 1


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
    assert resultado["next_action"] == "recopilar_datos"
    assert resultado["incident_id"] is None
    assert resultado["category"] == "hardware"
    assert resultado["follow_up_questions"]
    assert resultado["recommended_actions"]


def test_diagnostico_de_red_distingue_fallo_dns_con_evidencia_reportada():
    resultado = AgenteSoporteTI().responder(
        "No tengo internet",
        "USR-1042",
        {
            "network_checks": {
                "gateway_reachable": True,
                "dns_resolution": False,
                "internet_reachable": False,
            }
        },
    )
    diagnostico = resultado["diagnosis"]
    assert "DNS" in diagnostico["hypotheses"][0]["cause"]
    assert any("El usuario reporta" in evidencia for evidencia in resultado["evidence"])
    assert "Compara la resolucion" in " ".join(diagnostico["tests"])
    assert resultado["confidence"] == 0.82


def test_diagnostico_de_red_distingue_puerta_de_enlace_y_salida_a_internet():
    agente = AgenteSoporteTI()
    puerta_caida = agente.responder(
        "No tengo internet",
        "USR-1042",
        {"network_checks": {"gateway_reachable": False}},
    )
    salida_caida = agente.responder(
        "No tengo internet",
        "USR-1042",
        {
            "network_checks": {
                "gateway_reachable": True,
                "dns_resolution": True,
                "internet_reachable": False,
            }
        },
    )
    assert "puerta de enlace" in puerta_caida["diagnosis"]["hypotheses"][0]["cause"]
    assert "aguas arriba" in salida_caida["diagnosis"]["hypotheses"][0]["cause"]


def test_preguntas_de_seguimiento_respetan_contexto_y_no_piden_secretos():
    resultado = AgenteSoporteTI().responder(
        "No tengo internet",
        "USR-1042",
        {
            "operating_system": "Windows 11",
            "affected_scope": "solo mi equipo",
            "error_message": "Sin conexion",
            "recent_changes": "Ninguno",
        },
    )
    assert resultado["follow_up_questions"] == []
    assert resultado["next_action"] == "seguir_pasos_seguros"


def test_agente_escala_caso_sin_guia():
    resultado = AgenteSoporteTI().responder("La cafetera no funciona", "USR-1042")
    assert resultado["sources"] == ["protocolo_escalamiento"]
    assert resultado["needs_approval"] is True
    assert resultado["next_action"] == "borrador_pendiente_aprobacion"
    assert resultado["incident_id"] is None
    assert resultado["escalation_reason"]


def test_incidente_de_phishing_recibe_prioridad_alta():
    resultado = AgenteSoporteTI().responder(
        "Recibi un correo sospechoso con un enlace sospechoso",
        "USR-1042",
    )
    assert resultado["category"] == "ciberseguridad"
    assert resultado["priority"] == "high"
    assert resultado["recommended_actions"]


def test_health():
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_inicio_sirve_interfaz_grafica():
    respuesta = client.get("/")
    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
    assert "¿En qué podemos ayudarte?" in respuesta.text
    assert "Datos para afinar el diagnóstico" in respuesta.text
    assert "gateway-check" in respuesta.text
    assert "collectContext()" in respuesta.text
    assert 'fetch("/agent/chat"' in respuesta.text
    assert "Hermes + Kimi" in respuesta.text


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
    assert datos["category"] == "redes"
    assert datos["incident_id"] is None
    assert 0 <= datos["confidence"] <= 1
    assert datos["diagnosis"]["hypotheses"]
    assert datos["follow_up_questions"]


def test_agent_ask_rechaza_question_faltante():
    respuesta = client.post("/agent/ask", json={"user_id": "USR-1042"})
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Solicitud invalida."


def test_chat_hermes_enriquece_diagnostico_local_con_kimi(monkeypatch):
    def respuesta_modelo(question, diagnostico, history):
        assert question == "No tengo internet"
        assert diagnostico["sources"] == ["kb_internet_001"]
        assert history == [{"role": "user", "content": "Tengo problemas de red"}]
        return "La hipótesis principal es DNS; aún no está confirmada."

    monkeypatch.setattr(main_module, "generar_respuesta", respuesta_modelo)
    respuesta = client.post(
        "/agent/chat",
        json={
            "question": "No tengo internet",
            "user_id": "USR-1042",
            "context": {
                "network_checks": {
                    "gateway_reachable": True,
                    "dns_resolution": False,
                    "internet_reachable": False,
                }
            },
            "history": [
                {"role": "user", "content": "Tengo problemas de red"}
            ],
        },
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["answer"].startswith("La hipótesis principal")
    assert datos["diagnosis"]["hypotheses"][0]["cause"].startswith(
        "La resolucion DNS"
    )
    assert datos["sources"] == ["kb_internet_001"]


def test_chat_hermes_solo_acepta_acceso_loopback():
    remote_client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("192.168.1.10", 8001),
    )
    respuesta = remote_client.post(
        "/agent/chat",
        json={"question": "No tengo internet", "user_id": "USR-1042"},
    )
    assert respuesta.status_code == 403


def test_chat_hermes_informa_fallo_del_modelo_sin_degradarse_silenciosamente(monkeypatch):
    def fallo_modelo(question, diagnostico, history):
        assert question == "No tengo internet"
        assert diagnostico["sources"] == ["kb_internet_001"]
        assert history == []
        raise hermes_bridge.HermesBridgeError("Kimi no esta disponible.")

    monkeypatch.setattr(main_module, "generar_respuesta", fallo_modelo)
    respuesta = client.post(
        "/agent/chat",
        json={"question": "No tengo internet", "user_id": "USR-1042"},
    )
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == "Kimi no esta disponible."


def test_puente_hermes_lanza_cli_sin_herramientas_y_con_referencia_local(monkeypatch):
    capturado = {}

    def ejecutar(command, **kwargs):
        capturado["command"] = command
        capturado["kwargs"] = kwargs
        return hermes_bridge.subprocess.CompletedProcess(
            command, 0, stdout="Respuesta redactada por Kimi\n", stderr=""
        )

    monkeypatch.setattr(hermes_bridge, "_command", lambda prompt: ["hermes", "-z", prompt, "--toolsets", ""])
    monkeypatch.setattr(hermes_bridge.subprocess, "run", ejecutar)
    answer = hermes_bridge.generar_respuesta(
        "No tengo internet",
        {"sources": ["kb_internet_001"], "answer": "Usa solo pasos seguros."},
        [{"role": "user", "content": "No resuelve nombres"}],
    )
    command = capturado["command"]
    assert answer == "Respuesta redactada por Kimi"
    assert command[-2:] == ["--toolsets", ""]
    assert "kb_internet_001" in command[2]
    assert "No resuelve nombres" in command[2]
    assert capturado["kwargs"]["timeout"] == 180


def test_puente_hermes_explica_limite_de_kimi(monkeypatch):
    def rate_limited(command, **kwargs):
        return hermes_bridge.subprocess.CompletedProcess(
            command, 2, stdout="HTTP 429: rate-limited", stderr=""
        )

    monkeypatch.setattr(hermes_bridge, "_command", lambda prompt: ["hermes"])
    monkeypatch.setattr(hermes_bridge.subprocess, "run", rate_limited)
    with pytest.raises(hermes_bridge.HermesBridgeError, match="limite temporal"):
        hermes_bridge.generar_respuesta("No tengo internet", {}, [])


def test_comando_wsl_escapa_el_prompt_y_permite_fijar_distribucion(monkeypatch):
    monkeypatch.setattr(hermes_bridge.platform, "system", lambda: "Windows")
    monkeypatch.setattr(hermes_bridge.shutil, "which", lambda _: "wsl.exe")
    monkeypatch.setenv("SOPORTE_HERMES_WSL_DISTRO", "Ubuntu")

    command = hermes_bridge._command("texto ' ; no ejecutar")

    assert command[:4] == ["wsl.exe", "--distribution", "Ubuntu", "--exec"]
    assert command[-3:-1] == ["bash", "-lc"]
    assert "exec hermes -z" in command[-1]
    assert "no ejecutar" in command[-1]
    assert "--toolsets ''" in command[-1]


def test_herramienta_mcp_consulta_el_diagnostico_compartido():
    resultado = consultar_soporte_ti(
        "No tengo internet en mi portatil",
        "USR-1042",
        {"device": "portatil"},
    )

    assert resultado["sources"] == ["kb_internet_001"]
    assert resultado["needs_approval"] is False
    assert resultado["next_action"] == "recopilar_datos"


def test_herramienta_mcp_escala_casos_sin_guia():
    resultado = consultar_soporte_ti("La cafetera no funciona", "USR-1042")

    assert resultado["sources"] == ["protocolo_escalamiento"]
    assert resultado["needs_approval"] is True
    assert resultado["next_action"] == "borrador_pendiente_aprobacion"


def test_lambda_retorna_el_contrato_v13():
    respuesta = lambda_handler(
        {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/agent/ask",
            "body": json.dumps(
                {"question": "No tengo internet", "user_id": "USR-1042"}
            ),
        },
        None,
    )
    assert respuesta["statusCode"] == 200
    datos = json.loads(respuesta["body"])
    assert datos["category"] == "redes"
    assert datos["incident_id"] is None
    assert "hypotheses" in datos["diagnosis"]