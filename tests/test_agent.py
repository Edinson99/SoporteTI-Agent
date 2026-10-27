"""Pruebas del flujo objetivo -> herramientas -> resultado -> limites."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.hermes_bridge as hermes_bridge
from app.agent import AgenteSoporteTI
from app.lambda_handler import handler as lambda_handler
from app.main import AgentAskResponse, app
from app.mcp_server import consultar_soporte_ti
from app.tickets import TicketService
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
        "No resuelve DNS corporativo": "kb_l2_red_enrutamiento_dns_001",
        "El disco hace clic y no puedo recuperar archivos": "kb_l2_recuperacion_datos_001",
        "Error SAP GUI al conectarme al ERP": "kb_l2_software_especializado_erp_001",
        "La GPO no aplica en mi equipo": "kb_l2_politicas_gpo_permisos_001",
        "Outlook no funciona en el celular": "kb_corp_correo_movil_001",
        "Error al firmar PDF con certificado digital": "kb_corp_firma_digital_pdf_001",
        "No puedo compartir pantalla en Teams": "kb_corp_teams_zoom_audio_pantalla_001",
        "Moodle no sube la tarea": "kb_acad_moodle_canvas_archivo_001",
        "El proyector HDMI del aula no da imagen": "kb_acad_proyector_hdmi_aula_001",
        "Excel se congela con macro en xlsm": "kb_fin_excel_macro_xlsm_congelado_001",
        "Error al exportar CSV del ERP": "kb_fin_exportar_reporte_erp_csv_001",
        "Error de sincronizacion de nomina": "kb_fin_sincronizacion_nomina_001",
        "Docker dice port is already allocated": "kb_tech_docker_vscode_puertos_001",
        "La tarjeta grafica no aparece": "kb_tech_gpu_ram_diagnostico_001",
    }

    for pregunta, articulo_esperado in casos.items():
        articulo = buscar_conocimiento(pregunta)
        assert articulo is not None, pregunta
        assert articulo["id"] == articulo_esperado


def test_guias_nuevas_evitan_cambios_de_alto_impacto():
    articulos = {
        articulo["id"]: articulo
        for articulo in cargar_base_conocimiento()
    }

    assert any("no cambies rutas ni DNS" in paso for paso in articulos["kb_l2_red_enrutamiento_dns_001"]["pasos"])
    assert any("No ejecutes herramientas de reparacion" in paso for paso in articulos["kb_l2_recuperacion_datos_001"]["pasos"])
    assert any("no cambies el registro" in paso.casefold() for paso in articulos["kb_l2_politicas_gpo_permisos_001"]["pasos"])
    assert any("unicamente si tu mismo" in paso for paso in articulos["kb_corp_correo_movil_001"]["pasos"])
    assert any("No detengas procesos" in paso for paso in articulos["kb_tech_docker_vscode_puertos_001"]["pasos"])
    assert any("no actualices BIOS/UEFI" in paso for paso in articulos["kb_tech_gpu_ram_diagnostico_001"]["pasos"])


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
    assert 'fetch("/agent/tickets"' in respuesta.text
    assert 'href="/tickets"' in respuesta.text
    assert "Hermes + Kimi" in respuesta.text


def test_panel_de_seguimiento_se_sirve_solo_en_loopback():
    respuesta = client.get("/tickets")
    assert respuesta.status_code == 200
    assert "Marcar resuelto" in respuesta.text
    assert 'fetch("/api/tickets")' in respuesta.text


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


def test_agent_ask_solicita_contacto_antes_de_crear_ticket():
    respuesta = client.post(
        "/agent/ask",
        json={"question": "La cafetera no funciona", "user_id": "USR-1042"},
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["needs_approval"] is True
    assert datos["incident_id"] is None
    assert datos["ticket_email_status"] is None
    assert datos["contact_required"] is True
    assert datos["ticket_request_id"]


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


def test_chat_sin_guia_solicita_contacto_y_no_guarda_antes_de_autorizar(
    tmp_path, monkeypatch
):
    service = TicketService(tmp_path / "tickets.sqlite3")
    monkeypatch.setattr(main_module, "ticket_service", service)
    calls = []

    def respuesta_modelo(question, diagnostico, history):
        calls.append((question, diagnostico["needs_approval"], history))
        return "No encuentro una guía suficiente. ¿Quieres que contacte al técnico?"

    monkeypatch.setattr(main_module, "generar_respuesta", respuesta_modelo)
    respuesta = client.post(
        "/agent/chat",
        json={
            "question": "La cafetera no funciona",
            "user_id": "USR-1042",
            "history": [
                {"role": "user", "content": "El problema empezo esta manana"},
                {"role": "assistant", "content": "¿Que ocurre al encenderla?"},
            ],
        },
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["contact_required"] is True
    assert datos["ticket_request_id"]
    assert datos["chat_model_status"] == "used"
    assert datos["answer"].startswith("No encuentro una guía")
    assert calls == [
        (
            "La cafetera no funciona",
            True,
            [
                {"role": "user", "content": "El problema empezo esta manana"},
                {"role": "assistant", "content": "¿Que ocurre al encenderla?"},
            ],
        )
    ]
    assert not service.database_path.exists()


def test_crear_ticket_exige_contacto_y_envia_conversacion(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_APP_PASSWORD", "")
    service = TicketService(tmp_path / "tickets.sqlite3")
    monkeypatch.setattr(main_module, "ticket_service", service)
    response = client.post(
        "/agent/tickets",
        json={
            "request_id": "25038ee8-92a5-4db4-b4b2-965983e367de",
            "question": "La cafetera no funciona",
            "user_id": "USR-1042",
            "consent_to_email": True,
            "history": [
                {"role": "user", "content": "El problema empezo esta manana"},
                {"role": "assistant", "content": "¿Que ocurre al encenderla?"},
            ],
            "contact": {
                "name": "Javier Perez",
                "email": "javier@example.com",
                "phone": "+57 300 123 4567",
            },
        },
    )

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["ticket_number"].startswith("STI-")
    assert ticket["email_status"] == "not_configured"
    with sqlite3.connect(service.database_path) as connection:
        row = connection.execute(
            """
            SELECT contact_name, contact_email, contact_phone, conversation_json
            FROM tickets WHERE ticket_number = ?
            """,
            (ticket["ticket_number"],),
        ).fetchone()
    assert row[:3] == ("Javier Perez", "javier@example.com", "+57 300 123 4567")
    assert "El problema empezo esta manana" in row[3]
    assert "La cafetera no funciona" in row[3]


def test_crear_ticket_rechaza_contacto_invalido_y_consultas_con_guia():
    missing_contact = client.post(
        "/agent/tickets",
        json={
            "request_id": "25038ee8-92a5-4db4-b4b2-965983e367de",
            "question": "La cafetera no funciona",
            "user_id": "USR-1042",
            "consent_to_email": True,
        },
    )
    assert missing_contact.status_code == 400

    known_issue = client.post(
        "/agent/tickets",
        json={
            "request_id": "25038ee8-92a5-4db4-b4b2-965983e367df",
            "question": "No tengo internet",
            "user_id": "USR-1042",
            "consent_to_email": True,
            "contact": {
                "name": "Javier Perez",
                "email": "javier@example.com",
                "phone": "+57 300 123 4567",
            },
        },
    )
    assert known_issue.status_code == 409


def test_crear_ticket_requiere_consentimiento_explicito(tmp_path, monkeypatch):
    service = TicketService(tmp_path / "tickets.sqlite3")
    monkeypatch.setattr(main_module, "ticket_service", service)
    response = client.post(
        "/agent/tickets",
        json={
            "request_id": "45038ee8-92a5-4db4-b4b2-965983e367de",
            "question": "La cafetera no funciona",
            "user_id": "USR-1042",
            "consent_to_email": False,
            "contact": {
                "name": "Javier Perez",
                "email": "javier@example.com",
                "phone": "+57 300 123 4567",
            },
        },
    )

    assert response.status_code == 403
    assert not service.database_path.exists()


def test_panel_de_tickets_lista_y_marca_resuelto(tmp_path, monkeypatch):
    service = TicketService(tmp_path / "tickets.sqlite3")
    monkeypatch.setattr(main_module, "ticket_service", service)
    created = client.post(
        "/agent/tickets",
        json={
            "request_id": "35038ee8-92a5-4db4-b4b2-965983e367de",
            "question": "La cafetera no funciona",
            "user_id": "USR-1042",
            "consent_to_email": True,
            "contact": {
                "name": "Javier Perez",
                "email": "javier@example.com",
                "phone": "+57 300 123 4567",
            },
        },
    ).json()

    listed = client.get("/api/tickets")
    assert listed.status_code == 200
    assert listed.json()[0]["ticket_number"] == created["ticket_number"]
    resolved = client.post(
        f"/api/tickets/{created['ticket_number']}/resolve",
        json={"note": "Se restablecio el cable de alimentacion."},
    )

    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolution_note"] == "Se restablecio el cable de alimentacion."
    assert resolved.json()["resolved_at"]


def test_rutas_de_tickets_solo_aceptan_loopback():
    remote_client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("192.168.1.10", 8001),
    )
    assert remote_client.get("/tickets").status_code == 403
    assert remote_client.get("/api/tickets").status_code == 403


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