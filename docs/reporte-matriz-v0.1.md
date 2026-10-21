# Reporte de Matriz - SoporteTI-Agent v0.1

| Componente | Entrada | Salida esperada | Responsable | Evidencia o prueba |
| --- | --- | --- | --- | --- |
| `GET /health` | Sin cuerpo | `200` y `{"status":"ok"}` | Backend/API | `test_health`. |
| `POST /agent/ask` | `question`, `user_id`, `context` opcional | Pasos, fuente, aprobacion y siguiente accion | Backend/contrato | `test_agent_ask_retorna_diagnostico_ti`. |
| Herramienta MCP | Incidencia desde Hermes | Mismo diagnostico de la API, por stdio | Integracion Hermes | `test_herramienta_mcp_consulta_el_diagnostico_compartido`, `test_herramienta_mcp_escala_casos_sin_guia`. |
| Validacion | JSON incompleto o invalido | `400` con detalle legible | Backend/API | `test_agent_ask_rechaza_question_faltante`. |
| Conocimiento | Pregunta de soporte | Articulo local o escalacion | Datos/herramientas | `test_busca_conocimiento_de_internet`. |
| Limites | Caso sin guia | Borrador local y aprobacion humana | Orquestacion | `test_agente_escala_caso_sin_guia`. |
| JSON | Request y response de ejemplo | Contratos validos | Datos/contrato | `test_ejemplos_json_son_validos_y_contienen_el_contrato`. |
| Configuracion | `.env.example` | Variables sin secretos | Configuracion/seguridad | `.gitignore` excluye `.env` y `.venv/`. |
| Repositorio | Cambios probados | Commit y remoto actualizado | Integracion/Git | `git status`, `git log --oneline`, `git push`. |

## Mapa y pendiente

El [mapa de arquitectura](arquitectura.md) muestra el recorrido API -> validacion -> agente -> herramienta -> conocimiento o escalacion. La v0.1 no persiste tickets ni autentica usuarios; esos componentes deben incorporarse antes de un despliegue productivo.