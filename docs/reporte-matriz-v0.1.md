# Reporte de Matriz - SoporteTI-Agent v0.1

Esta matriz relaciona cada superficie del producto con su contrato, limite y
verificacion. La API HTTP, Lambda y MCP comparten el mismo agente y la misma
base de conocimiento; Hermes/Kimi es el canal conversacional opcional.

## Matriz de componentes y verificacion

| Componente / tema | Entrada o condicion | Salida o comportamiento esperado | Modulo / responsable | Evidencia |
| --- | --- | --- | --- | --- |
| API `GET /health` | Solicitud sin cuerpo | HTTP `200`, `{"status":"ok"}` | `app/main.py` | `test_health`. |
| API `POST /agent/ask` | `question`, `user_id`, `context` opcional | Respuesta validada con `answer`, `sources`, `needs_approval`, `next_action` | FastAPI / Pydantic | `test_agent_ask_retorna_diagnostico_ti`. |
| Validacion HTTP y MCP | Pregunta de 5-500 caracteres; usuario de 3-50; contexto opcional tipo objeto | HTTP `400` legible para errores HTTP; MCP valida con Pydantic y reporta error de herramienta | `AgentAskRequest` | `test_agent_ask_rechaza_question_faltante`; validacion compartida en `app/mcp_server.py`. |
| Lambda/API Gateway | Evento HTTP API con ruta y cuerpo JSON | `GET /health`, `POST /agent/ask`, error `400`/`404` segun evento | `app/lambda_handler.py`, `template.yaml` | Handler comparte `AgentAskRequest`, `AgentAskResponse` y `AgenteSoporteTI`; no cuenta con prueba dedicada en `tests/test_agent.py`. |
| Adaptador MCP | Hermes inicia `python -m app.mcp_server` por stdio | Herramienta `consultar_soporte_ti` con el mismo diagnostico | `app/mcp_server.py` | `test_herramienta_mcp_consulta_el_diagnostico_compartido`; verificacion operativa `hermes mcp test soporte_ti`. |
| Seleccion de articulos | Incidencia que coincide con palabras clave | Articulo mas especifico; no acepta coincidencias parciales dentro de otras palabras | `app/tools.py` | `test_busca_conocimiento_de_internet`; `test_base_conocimiento_incluye_guias_ti_frecuentes`; `test_busqueda_no_coincide_con_palabras_parciales`. |
| Conocimiento de soporte | Problema cubierto por JSON versionado | Pasos seguros con el ID del articulo en `sources` | `data/conocimiento_soporte.json` | Busquedas de articulos cubiertas por `test_base_conocimiento_incluye_guias_ti_frecuentes`. |
| Formateo/reinstalacion | Solicitud de formatear o reinstalar | Recomienda no iniciar el borrado sin autorizacion y respaldo verificado | `kb_formateo_reinstalacion_001` | `test_guias_de_formateo_y_cmd_indican_limites_seguros`. |
| Copias de seguridad | Solicitud de respaldo/restauracion | Usa almacenamiento aprobado y comprueba copia antes de cambios | `kb_respaldo_datos_001` | `test_base_conocimiento_incluye_guias_ti_frecuentes`. |
| Licencias | Licencia expirada o error de activacion | Verificacion institucional; no comparte claves ni usa activadores | `kb_licencias_activacion_001` | `test_base_conocimiento_incluye_guias_ti_frecuentes`. |
| Comandos CMD | Pregunta por `ipconfig`, `ping`, `hostname`, `whoami` o `systeminfo` | Explica consultas informativas; advierte no ejecutar comandos destructivos | `kb_cmd_diagnostico_001` | `test_guias_de_formateo_y_cmd_indican_limites_seguros`. |
| Optimizacion | Rendimiento, inicio o recursos del equipo | Acciones manuales de bajo riesgo; no limpiadores, registro ni desactivar seguridad | `kb_optimizacion_equipo_001` | `test_base_conocimiento_incluye_guias_ti_frecuentes`. |
| Escalacion | No existe coincidencia en la base de conocimiento | Borrador no persistente, aprobacion humana requerida; no crea ticket | `app/agent.py`, `app/tools.py` | `test_agente_escala_caso_sin_guia`; `test_herramienta_mcp_escala_casos_sin_guia`. |
| Contratos JSON | Ejemplos de solicitud y respuesta | JSON parseable con campos esperados | `data/agent_request.json`, `data/agent_response.json` | `test_ejemplos_json_son_validos_y_contienen_el_contrato`. |
| Kimi + Hermes | Kimi configurado como proveedor de Hermes; MCP configurado en `~/.hermes/config.yaml` | Hermes conversa con el modelo e invoca MCP cuando se le solicita | Configuracion local del usuario | Guia tecnica y prueba manual `hermes mcp list`, `hermes mcp test soporte_ti`; la API de Kimi no se invoca desde las pruebas automatizadas. |
| Pruebas automatizadas | Entorno Python del proyecto | Suite de `tests/test_agent.py` | Pytest | Ultima ejecucion documentada: 12 pruebas pasaron; ejecutar de nuevo tras cambios. |
| Seguridad de credenciales | Configuracion local | Claves fuera del repositorio; `.env` y entornos virtuales ignorados por Git | Hermes / `.gitignore` | Revision de `.gitignore`; nunca incluir valores secretos en commits. |
| Documentacion operativa | Instalacion, configuracion, uso y limites | Instrucciones diferenciadas para administradores y usuarios | `docs/guia-tecnica-hermes-kimi.md`, `docs/guia-usuario-hermes-kimi.md` | Revision documental y enlaces desde `README.md`. |

## Temas cubiertos por la base de conocimiento

La base versionada incluye articulos para internet, rendimiento, impresora,
correo, acceso a cuenta, autenticacion multifactor, VPN, instalacion de
software, perifericos, correos sospechosos/phishing, pantalla azul o
actualizacion, bateria/carga, formateo/reinstalacion, respaldo, licencias,
comandos de diagnostico CMD y optimizacion. Si una pregunta no coincide con
las palabras clave de un articulo, el agente escala en lugar de inventar un
procedimiento.

## Limites, dependencias y pendientes

- La busqueda es determinista por palabras clave; no es una busqueda semantica
  ni una consulta a Kimi. Preguntas ambiguas o con varios temas pueden
  necesitar reformulacion o revision humana.
- Los borradores de escalacion viven solo durante la solicitud y no se guardan
  ni se envian a una mesa de ayuda.
- El contrato HTTP no implementa autenticacion. No debe exponerse publicamente
  sin incorporar autenticacion, autorizacion, controles de uso y transporte
  seguro.
- La integracion MCP descrita es stdio local. No publica un servidor remoto.
- Kimi es opcional para el backend y se configura en Hermes. Su clave no debe
  incluirse en archivos versionados ni en evidencia de pruebas.
- La matriz solo atribuye cobertura automatizada a las pruebas existentes; la
  prueba de Hermes/Kimi y la prueba de Lambda son verificaciones operativas o
  pendientes de automatizacion.

Consulta el [mapa de arquitectura](arquitectura.md) para ver los adaptadores
HTTP, Lambda y MCP y el recorrido compartido de diagnostico. Los pasos de
instalacion estan en la [guia tecnica](guia-tecnica-hermes-kimi.md) y el inicio
cotidiano en la [guia para usuarios](guia-usuario-hermes-kimi.md).