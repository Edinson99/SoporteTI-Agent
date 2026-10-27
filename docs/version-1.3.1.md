# Version 1.3.1

La version 1.3.1 integra el chat web existente con Hermes y el modelo
configurado en esa instalacion (Kimi en la configuracion documentada), sin
reemplazar la interfaz ni el diagnostico local de la version 1.3.0.

## Integracion del chat

- La interfaz web usa `POST /agent/chat`.
- FastAPI genera primero el diagnostico estructurado con el agente y la base
  local de conocimiento.
- El backend invoca Hermes CLI en WSL para redactar la respuesta a partir de
  la consulta, el diagnostico local y hasta diez mensajes anteriores.
- La interfaz presenta la respuesta redactada junto con las fuentes,
  hipotesis, evidencia y acciones recomendadas del diagnostico local.
- `POST /agent/ask` permanece disponible como endpoint determinista, sin
  requerir Hermes ni un modelo de lenguaje.

Hermes debe estar instalado y configurado en WSL con un proveedor y modelo
disponibles. En la configuracion descrita en la guia, el modelo es Kimi. El
historial solo se conserva en memoria en la pagina y se pierde al recargar.

## Seguridad, privacidad y limites

- `POST /agent/chat` acepta conexiones de loopback; el servidor de desarrollo
  tambien se inicia enlazado a `127.0.0.1`.
- El backend deshabilita las herramientas de Hermes durante la consulta web.
  Kimi redacta la respuesta, pero no diagnostica directamente, ejecuta
  comandos ni invoca herramientas MCP desde esta ruta.
- La pregunta, el diagnostico local y el historial se envian al proveedor
  configurado en Hermes. `user_id` no se incluye en el prompt y la clave API
  permanece en Hermes, fuera del navegador.
- Si Hermes o el proveedor no estan disponibles, el endpoint devuelve un
  error explicito; no presenta la respuesta local como si la hubiera generado
  el modelo.
- Esta integracion no agrega ejecucion remota, persistencia de conversaciones,
  autenticacion, tickets persistentes ni comprobaciones del equipo. No envies
  contrasenas, codigos MFA, claves, tokens ni datos confidenciales.
- La herramienta MCP existente continua disponible para sesiones interactivas
  de Hermes; es independiente del flujo del chat web.

## Verificacion y configuracion

La suite automatizada cubre el puente con Hermes, el contexto y el historial,
el acceso limitado a loopback y los errores del proveedor, ademas de las
pruebas existentes del agente. Ejecuta desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

Consulta el [contrato HTTP](api-contract.md), la
[guia tecnica de Hermes y Kimi](guia-tecnica-hermes-kimi.md) y la
[guia de usuario](guia-usuario-hermes-kimi.md) para los detalles de uso y
configuracion.
