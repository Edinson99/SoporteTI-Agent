# Contrato de la API v1.3.0

## `GET /health`

No recibe cuerpo y responde `200`:

```json
{"status": "ok"}
```

## `POST /agent/ask`

Busca guias locales, plantea hipotesis y pruebas provisionales, y solicita los
datos faltantes o revision humana.

### Entrada

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

| Campo | Tipo | Obligatorio | Uso |
| --- | --- | --- | --- |
| `question` | texto | Si | Problema de soporte, entre 5 y 500 caracteres. |
| `user_id` | texto | Si | Identificador declarado por el cliente; no autentica al usuario. |
| `context` | objeto | No | Datos del equipo, alcance, error, cambios recientes o pruebas reportadas. |

### Respuesta `200`

```json
{
  "answer": "Para portatil: 1. Verifica si otro dispositivo puede conectarse a la misma red.",
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
    "tests": ["Comprueba si otros dispositivos tienen conectividad."]
  },
  "evidence": ["Palabra clave coincidente: internet"],
  "confidence": 0.59,
  "recommended_actions": ["Verifica si otro dispositivo puede conectarse a la misma red."],
  "escalation_reason": null,
  "follow_up_questions": ["¿Que sistema operativo y version utilizas?"]
}
```

La respuesta contiene `incident_id` (actualmente `null`), `category`,
`priority`, `diagnosis` (resumen, hipotesis y pruebas), `evidence`,
`confidence`, `recommended_actions`, `escalation_reason` y
`follow_up_questions`, ademas de `answer`, `sources`, `needs_approval` y
`next_action`. La confianza es heuristica y refleja coincidencia con guias; no
es una probabilidad calibrada ni confirma la causa raiz.

### Contexto opcional

`context` puede contener `device`, `operating_system`, `affected_scope`,
`error_message`, `recent_changes` y `network_checks`. Este ultimo puede incluir
los booleanos `gateway_reachable`, `dns_resolution` e `internet_reachable`;
son resultados proporcionados por el usuario, no pruebas ejecutadas o
verificadas por el servidor.

### Respuesta de caso sin guia

La API prepara solo un borrador en memoria y devuelve `needs_approval: true`,
`next_action: "borrador_pendiente_aprobacion"` y el motivo en
`escalation_reason`. No se asigna `incident_id` ni se persiste un ticket.

### Errores

| Estado | Significado |
| --- | --- |
| `400` | JSON invalido, campo obligatorio ausente o tipo incorrecto. |
| `500` | Fallo interno no controlado. |

## Limites

El agente no autentica `user_id`, no persiste incidencias, no ejecuta comandos,
instala software, cambia contrasenas, modifica configuraciones criticas,
elimina archivos ni envia tickets automaticamente. Las acciones de cambio
requieren intervencion o aprobacion humana.
