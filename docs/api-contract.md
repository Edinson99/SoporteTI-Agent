# API Contract

Contrato de API de SoporteTI-Agent v1.3.1.

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

- `incident_id`: `null` mientras no haya un sistema de tickets persistente.
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
- `400`: JSON invalido o falta un campo obligatorio.
- `500`: fallo interno no controlado.

## Contexto opcional

Además de `device` y `operating_system`, puede incluirse `affected_scope`,
`error_message`, `recent_changes` y `network_checks`. Este último acepta los
valores booleanos `gateway_reachable`, `dns_resolution` e
`internet_reachable`. Son resultados reportados por el usuario: el servidor no
ejecuta comandos ni comprueba conectividad.

La API no autentica `user_id`, no persiste incidencias, no ejecuta comandos,
instala software, cambia contraseñas ni envía tickets automáticamente.

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
deshabilitadas en el modo de una sola consulta. El diagnóstico local es la
fuente de conocimiento; Kimi solo lo redacta. El historial se mantiene en la
memoria de la página y no se guarda en el servidor.