# API Contract

Contrato de API de SoporteTI-Agent v1.3.3.

## `GET /health`

- Entrada: ninguna.
- Salida: `{"status":"ok"}`.
- Estado exitoso: `200`.

## `POST /agent/ask`

### Entrada JSON

```json
{
  "question": "No tengo internet en mi portatil",
  "user_id": "USR-1042",
  "context": {
    "device": "portatil",
    "operating_system": "Windows 11"
  }
}
```

- `question`: texto obligatorio de la incidencia.
- `user_id`: texto obligatorio para identificar el caso.
- `context`: objeto opcional con datos del equipo.

### Salida JSON `200`

```json
{
  "answer": "Para portatil: sigue los pasos seguros de la base de conocimiento.",
  "sources": ["kb_internet_001"],
  "needs_approval": false,
  "next_action": "recopilar_datos",
  "incident_id": null,
  "ticket_email_status": null,
  "ticket_request_id": null,
  "contact_required": false,
  "chat_model_status": null,
  "category": "redes",
  "priority": "normal",
  "diagnosis": {
    "summary": "La descripcion coincide con un problema de conectividad de red o Internet. La causa raiz aun no esta confirmada.",
    "hypotheses": [
      {
        "cause": "Problema de conectividad de red o Internet",
        "confidence": 0.59,
        "sources": ["kb_internet_001"],
        "rationale": "Coincidencia heuristica de palabras clave; no confirma la causa.",
        "tests": ["Compara el resultado con otro equipo de la misma red."]
      }
    ],
    "tests": ["Comprueba si otros dispositivos de la misma red tienen conectividad."]
  },
  "evidence": ["Palabra clave coincidente: internet"],
  "confidence": 0.59,
  "recommended_actions": ["Verifica si otro dispositivo puede conectarse a la misma red."],
  "escalation_reason": null,
  "follow_up_questions": [
    "¿Que sistema operativo y version utilizas?",
    "¿Afecta solo a tu equipo o tambien a otras personas o equipos?"
  ]
}
```

- `incident_id`: se asigna al confirmar los datos de contacto en `POST /agent/tickets`.
- `ticket_email_status`: estado del correo después de confirmar el ticket.
- `ticket_request_id`: identificador temporal para que un reintento de confirmación no cree tickets duplicados.
- `contact_required`: indica que no se encontró guía y el chat debe solicitar nombre, correo y teléfono.
- `chat_model_status`: `not_used_escalation` cuando no se requiere Hermes/Kimi para presentar el formulario; `used` para respuestas de consultas con guía.
- `category` y `priority`: clasificación heurística del caso.
- `diagnosis`: resumen, hipótesis ordenadas y pruebas sugeridas; no afirma una causa confirmada.
- `evidence`: palabras coincidentes y resultados de diagnóstico que el usuario haya reportado.
- `confidence`: fuerza heurística de la hipótesis principal, no probabilidad calibrada.
- `recommended_actions`: pasos de la guía local coincidente.
- `follow_up_questions`: datos faltantes para continuar el diagnóstico.
- `escalation_reason`: motivo de escalación, si aplica.
- `answer`, `sources`, `needs_approval` y `next_action` conservan su propósito.

### Estados

- `200`: solicitud procesada, incluso cuando se prepara una escalacion.
- `422`: JSON invalido, falta un campo obligatorio o un valor no pasa validacion.
- `500`: fallo interno no controlado.

## Contexto opcional

Además de `device` y `operating_system`, puede incluirse `affected_scope`,
`error_message`, `recent_changes` y `network_checks`. Este último acepta los
valores booleanos `gateway_reachable`, `dns_resolution` e
`internet_reachable`. Son resultados reportados por el usuario: el servidor no
ejecuta comandos ni comprueba conectividad.

La API no autentica `user_id`; el identificador es el texto enviado por el
solicitante. El endpoint de diagnóstico no crea tickets automáticamente. El
ticket local y su correo se generan después de que el usuario entrega sus
datos de contacto en el chat.

## `POST /agent/chat`

Ruta local de la interfaz web. Debe llamarse desde loopback; otros clientes
reciben `403`. Valida `question`, `user_id` y el mismo `context` de diagnóstico,
y acepta opcionalmente hasta diez mensajes previos:

```json
{
  "question": "No tengo internet",
  "user_id": "USR-1042",
  "context": {
    "operating_system": "Windows 11",
    "network_checks": {
      "gateway_reachable": true,
      "dns_resolution": false,
      "internet_reachable": false
    }
  },
  "history": [
    {"role": "user", "content": "Tengo problemas de conexión"},
    {"role": "assistant", "content": "Vamos a revisar los datos disponibles."}
  ]
}
```

El servidor calcula primero el diagnóstico determinista con la base local y
después invoca `hermes -z` en WSL para que el modelo configurado en Hermes
redacte `answer`. La respuesta conserva el resto del contrato de
`AgentAskResponse` para que la interfaz muestre hipótesis, evidencia y pasos
recomendados. Se envían al modelo la pregunta, el resultado local y el
historial; `user_id` no se incluye en el prompt. La API key permanece en Hermes.
Si Hermes/Kimi falla, devuelve `503`; no se presenta la respuesta local como si
fuera una respuesta del modelo.

Esta ruta de chat no invoca herramientas Hermes/MCP: las herramientas están
deshabilitadas en el modo de una sola consulta. Si no encuentra guía, devuelve
el diagnóstico local y un formulario requerido, sin invocar Hermes ni crear un
ticket. Para consultas con guía, Kimi redacta la respuesta y los errores de
Hermes se devuelven explícitamente.

### Tickets y notificaciones locales

El chat muestra campos obligatorios de nombre, correo y teléfono si no se
encuentra guía. Solo tras enviarlos llama `POST /agent/tickets`; así no se
guarda ni se envía el ticket antes de que el usuario facilite esos datos. La
conversación incluye el historial previo, la consulta y el mensaje de
escalamiento local. El correo también incluye los datos de contacto.

El endpoint es de loopback y rechaza consultas que ya tengan guía. `request_id`
hace idempotente la confirmación y evita tickets duplicados en reintentos. Los
tickets se guardan en `data/tickets.sqlite3` (o en `SOPORTE_TICKETS_DB`). Si el
correo no está configurado o falla, el ticket permanece guardado y la
respuesta devuelve su estado.

### `POST /agent/tickets`

Confirma la escalación del chat y crea el ticket únicamente si el diagnóstico
sigue sin encontrar una guía. Requiere loopback.

```json
{
  "question": "No puedo conectarme y ya reinicie el router",
  "user_id": "USR-1042",
  "context": {"operating_system": "Windows 11"},
  "history": [
    {"role": "user", "content": "Tengo problemas de conexión"},
    {"role": "assistant", "content": "¿Afecta a otros equipos?"}
  ],
  "request_id": "a762137a-4b3b-4fa2-9644-31a5ad019ff4",
  "contact": {
    "name": "Nombre del usuario",
    "email": "usuario@example.com",
    "phone": "+34 600 000 000"
  },
  "assistant_response": "El caso se enviará al técnico."
}
```

`request_id` es un UUID; `contact.name`, `contact.email` y `contact.phone`
son obligatorios y validados. `history` admite hasta diez mensajes. Respuesta
`201`:

```json
{
  "ticket_number": "STI-AAAAMMDD-000001",
  "email_status": "sent",
  "status": "open"
}
```

Los posibles valores de `email_status` son `pending`, `sent`, `failed` y
`not_configured`. `409` indica que existe una guía y no se creó el ticket;
`403` indica que la solicitud no procede de loopback; los errores de
validación usan `422`.

## Seguimiento de tickets

- `GET /tickets`: panel local del técnico.
- `GET /api/tickets`: lista tickets, contacto, conversación y estado.
- `POST /api/tickets/{ticket_number}/resolve`: guarda fecha y nota opcional de
  resolución.

El endpoint de resolución acepta `{"note": "Solución aplicada"}` (la nota es
opcional, máximo 1000 caracteres) y devuelve el número, el estado `resolved`,
la fecha de resolución y la nota.

El panel y sus endpoints de datos requieren una conexión de loopback, pero no
hay autenticación de técnicos. No expongas el servidor ni compartas el panel
con usuarios no autorizados.