# API Contract

Contrato de API de SoporteTI-Agent v1.4.0.

## `GET /health`

- Entrada: ninguna.
- Salida: `{"status":"ok"}`.
- Estado exitoso: `200`.
- Es un health check de vida de la API; no comprueba disponibilidad de
  Firebase, Hermes, Gmail ni otros proveedores.

## Estado y métricas

- `GET /status`: página de estado accesible sin credenciales.
- `GET /api/status`: estado general de la API, timestamp y configuración
  resumida de dependencias. Los proveedores externos se muestran como
  configurados/no configurados; no se consulta su disponibilidad ni se exponen
  nombres de host, DSN, tokens o direcciones de correo.
- `GET /api/metrics`: contadores por método, ruta parametrizada y código HTTP,
  latencia media/máxima y errores 5xx. Requiere loopback (`403` en remoto).
  Solo vive en memoria y no guarda IP, cuerpo, pregunta, identidad, imágenes o
  datos de contacto.
- Las rutas de diagnóstico, chat, confirmación de tickets, feedback y webhook
  tienen un límite por proceso de 60 solicitudes/minuto y origen de conexión,
  configurable con `SOPORTE_RATE_LIMIT_PER_MINUTE`. Al excederlo devuelven
  `429` y `Retry-After: 60`. No es un coordinador de límites distribuido.
- Sentry es opcional: configura `SENTRY_DSN` e instala
  `requirements-observability.txt`. Los eventos eliminan solicitud, identidad,
  mensajes, variables locales y breadcrumbs antes de salir del proceso.

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
- `contact_required`: el chat debe mostrar el formulario de contacto porque no hay guía suficiente, el usuario lo pidió explícitamente o ya respondió tres veces a las preguntas de seguimiento sin resolver la incidencia.
- `chat_model_status`: `used` en cada turno de `/agent/chat`, incluso si no se encuentra guía; `null` en el endpoint determinista `/agent/ask`.
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
  ],
  "attachments": [
    {
      "file_name": "error.png",
      "content_type": "image/png",
      "data_url": "data:image/png;base64,<contenido-base64>"
    }
  ]
}
```

El servidor calcula primero el diagnóstico determinista con la base local y
después invoca `hermes -z` en WSL en cada turno para que el modelo configurado
en Hermes (Kimi en la configuración recomendada) redacte `answer`, también
cuando no hay una guía. La respuesta conserva el resto del contrato de
`AgentAskResponse` para que la interfaz muestre hipótesis, evidencia y pasos
recomendados. Se envían al modelo la pregunta, el resultado local y el
historial de hasta diez mensajes, con un máximo de 4000 caracteres por mensaje;
`user_id` no se incluye en el prompt. La API key permanece en Hermes.
Si Hermes o el proveedor configurado falla, devuelve `503`; no se presenta la
respuesta local como si fuera una respuesta del modelo.
La respuesta del chat se redacta en espanol sin tildes ni `ñ`; la API elimina
diacriticos tambien de las preguntas de seguimiento que agrega el servidor.

Hermes se invoca con la herramienta web para buscar información solo si la guía
local no basta; cuando se adjuntan imágenes se habilita también la herramienta
de visión. No se habilitan terminal ni ejecución de comandos. Las imágenes se
guardan temporalmente durante el turno y se eliminan al terminar, incluso ante
un error. `attachments` admite hasta tres imágenes JPG, PNG o WebP de máximo
2 MiB cada una; se validan el MIME y la firma binaria. El contenido de una
imagen o página web se trata como dato no confiable. La interfaz solo hace
clicables enlaces HTTPS de dominios oficiales permitidos.

Si no encuentra guía, la interfaz hace una pregunta concreta para continuar
después de la primera consulta y mantiene el seguimiento durante tres
respuestas del usuario. Tras la tercera respuesta (cuarto mensaje del usuario,
contando la consulta inicial) muestra el formulario de contacto. Una petición
explícita para contactar al técnico permite mostrarlo antes. Todavía no crea ni
envía el ticket. Para consultas
con guía, el modelo redacta la respuesta; los errores de Hermes se devuelven
explícitamente. El historial y las capturas permanecen solo en la memoria de
la página mientras dura la sesión y se pierden al recargar.

### Valoraciones de guias

Las respuestas que usan una guia local muestran botones opcionales de utilidad.
El voto se asocia solo con la guia principal de la respuesta. El endpoint de
loopback `POST /api/feedback` acepta:

```json
{
  "article_id": "kb_internet_001",
  "rating": "useful"
}
```

`rating` acepta `useful` o `not_useful`; la guia debe existir en la base local.
Una respuesta correcta es `200 {"status":"recorded"}`. La ruta rechaza
solicitudes remotas con `403`, datos invalidos con `400` y fallos de
persistencia con `503`.

Por defecto, SQLite usa `data/feedback.sqlite3`, configurable con
`SOPORTE_FEEDBACK_DB`. Solo se persisten `article_id`, `rating` y `created_at`
en UTC; no se guarda pregunta, conversacion, usuario, contacto ni texto libre.
Los votos se eliminan al guardar un voto o consultar el resumen cuando superan
180 dias. `GET /api/feedback/summary` devuelve conteos agregados por guia y
tambien requiere loopback. Las valoraciones sirven para priorizar revision
humana; no actualizan articulos automaticamente.

### Tickets y notificaciones locales

El chat muestra campos obligatorios de nombre, correo, teléfono y autorización
explícita si no encuentra guía suficiente. Solo tras aceptar la autorización
y enviar el formulario llama `POST /agent/tickets`; así no se guarda ni se
envía el ticket antes de que el usuario lo autorice. El correo dirigido al
técnico incluye al usuario en copia (`Cc`). La conversación incluye el
historial previo, la consulta y la respuesta del asistente.

El endpoint es de loopback y rechaza una consulta que ya tenga guía si aún no
hubo tres respuestas de seguimiento y tampoco se pidió contacto explícitamente.
`request_id` hace idempotente la confirmación y evita tickets duplicados en reintentos. Por
defecto, los tickets se guardan en `data/tickets.sqlite3` (o en
`SOPORTE_TICKETS_DB`). Si el correo no está configurado o falla, el ticket
permanece guardado y la respuesta devuelve su estado.

#### Backend opcional Firebase Data Connect

Se puede seleccionar el backend con `SOPORTE_TICKETS_BACKEND=firebase`. Los
valores permitidos son `sqlite` (predeterminado) y `firebase`; un valor
desconocido impide iniciar la aplicación. La configuración de Firebase usa:

- `FIREBASE_PROJECT_ID`: proyecto, predeterminado `soporteit-tickets`.
- `DATA_CONNECT_SERVICE_ID`: servicio, predeterminado
  `soporteit-tickets-service`.
- `DATA_CONNECT_LOCATION`: ubicación, predeterminada `us-east4`.
- `NODE_BIN`: opcional, ruta completa a `node.exe` si Node no está en `PATH`.

El backend ejecuta las operaciones GraphQL del conector `support` mediante
Firebase Admin SDK y Application Default Credentials (ADC). `firebase login`
no configura ADC para el proceso de Python/Node. En desarrollo local inicia
sesión con Google Cloud CLI mediante `gcloud auth application-default login`;
en servidor usa identidad de workload y otorga solo los permisos necesarios
para invocar Data Connect. No almacenes claves de servicio en el repositorio.
Las operaciones usan acceso `NO_ACCESS` para clientes finales; el puente
privilegiado solo acepta operaciones incluidas en una lista cerrada.

Los tickets, mensajes, eventos de auditoría y parte del contexto se guardan en
las tablas existentes de Cloud SQL por medio de Data Connect. La operación de
creación del ticket y sus mensajes/eventos es transaccional. El correo se
intenta después de guardar y su resultado se persiste; un reintento con el
mismo `request_id` devuelve el ticket existente y no duplica el envío. El
número es `STI-AAAAMMDD-<UUID>` para Firebase y `STI-AAAAMMDD-######` para
SQLite. No se ejecutan migraciones ni se importan tickets SQLite al activar
Firebase.

Si Data Connect, ADC, Node.js o sus permisos no están disponibles, los
endpoints de tickets devuelven `503` explícito; no se cambia silenciosamente a
SQLite. `GET /health` solo comprueba la API y no valida Firebase. La plantilla
AWS SAM no empaqueta el puente Node ni configura identidad de workload; no
uses el backend Firebase desde ese despliegue sin preparar y proteger ambos.

### `POST /agent/tickets`

Confirma la escalación del chat cuando el diagnóstico no encuentra guía, tras
tres respuestas del usuario sin resolver la incidencia, o por solicitud
explícita de contacto. Requiere loopback y consentimiento.

```json
{
  "question": "No puedo conectarme y ya reinicie el router",
  "user_id": "USR-1042",
  "context": {"operating_system": "Windows 11"},
  "history": [
    {"role": "user", "content": "Tengo problemas de conexión"},
    {"role": "assistant", "content": "¿Afecta a otros equipos?"}
  ],
  "attachments": [
    {
      "file_name": "error.png",
      "content_type": "image/png",
      "data_url": "data:image/png;base64,<contenido-base64>"
    }
  ],
  "request_id": "a762137a-4b3b-4fa2-9644-31a5ad019ff4",
  "consent_to_email": true,
  "contact": {
    "name": "Nombre del usuario",
    "email": "usuario@example.com",
    "phone": "+34 600 000 000"
  },
  "assistant_response": "El caso se enviará al técnico."
}
```

`request_id` es un UUID; `consent_to_email` debe ser `true` para autorizar la
creación del ticket y el envío del correo al técnico con copia al usuario.
`contact.name`, `contact.email` y `contact.phone` son obligatorios y validados.
`history` admite hasta diez mensajes. `attachments` admite hasta tres imágenes
del mismo formato y tamaño validados para `/agent/chat`; solo se guardan tras
el consentimiento y se muestran desde el panel local. No se adjuntan al correo.
Respuesta
`201`:

```json
{
  "ticket_number": "STI-AAAAMMDD-000001",
  "email_status": "sent",
  "status": "open"
}
```

Los posibles valores de `email_status` son `pending`, `sent`, `failed` y
`not_configured`. La respuesta también incluye `email_provider` (`gmail`,
`resend` o `none`), `email_failure_class` (`none`, `not_configured`,
`configuration`, `transient` o `pending`) y `alert_status` (`sent`, `failed`,
`not_configured`, `skipped` o `pending`). `409` indica que existe una guía y no se creó el ticket;
`403` indica que la solicitud no procede de loopback o no incluye consentimiento; los errores de
validación usan `422`.

Gmail API OAuth es el proveedor primario. Si falta su configuración o falla el
envío, Resend se usa como respaldo solo si están configurados
`RESEND_API_KEY`, `RESEND_FROM` y `RESEND_TO_EMAIL`; el fallo queda clasificado
como configuración o transitorio y el estado/proveedor se guarda con el ticket.
La firma de Gmail se conserva en el proveedor primario. Los correos de respaldo
se envían al técnico con copia al contacto. Un fallo de ambos proveedores no
elimina el ticket.

`SLACK_WEBHOOK_URL` es opcional y se limita a webhooks HTTPS de
`hooks.slack.com`. Solo notifica prioridades `high`/`critical` y el mensaje
incluye ticket, prioridad y categoría; nunca descripción, conversación,
capturas o contacto. El resultado se persiste y audita.

## Seguimiento de tickets

- `GET /tickets`: panel local del técnico.
- `GET /api/tickets`: lista tickets, contacto, conversación y estado.
- `GET /api/tickets/{ticket_number}/attachments/{attachment_id}`: entrega una
  imagen del ticket a clientes locales; los bytes no se incluyen en el listado.
- `POST /api/tickets/{ticket_number}/resolve`: guarda fecha y nota opcional de
  resolución.

El endpoint de resolución acepta `{"note": "Solución aplicada"}` (la nota es
opcional, máximo 1000 caracteres) y devuelve el número, el estado `resolved`,
la fecha de resolución y la nota.

El panel y sus endpoints de datos requieren una conexión de loopback, pero no
hay autenticación de técnicos. No expongas el servidor ni compartas el panel
con usuarios no autorizados. Para Firebase Data Connect, las imágenes se
almacenan en los metadatos de contexto; para SQLite, en una tabla de adjuntos.
El endpoint las sirve solo desde conexiones locales. Las capturas se eliminan
al resolver el ticket o al superar 180 días; la limpieza se ejecuta al listar
tickets, crear/resolver tickets o consultar adjuntos.

## Canal Telegram

El cliente MTProto personal se inicia como proceso independiente mediante
`python -m scripts.telegram_mtproto`; no es un endpoint HTTP. Requiere
`TELEGRAM_MTPROTO_API_ID`, `TELEGRAM_MTPROTO_API_HASH` y una lista no vacía de
IDs numéricos en `TELEGRAM_MTPROTO_ALLOWED_USER_IDS`. La lista se aplica a
mensajes entrantes privados antes de procesar comandos. Solo `/start` y
`/consulta <problema>` reciben respuesta. La consulta usa las guías locales,
no llama a Hermes, no crea tickets y no guarda el texto ni el historial en la
aplicación. El archivo de sesión autenticada se conserva localmente bajo
`.secrets/telegram-mtproto.session` y debe protegerse como una credencial.

El endpoint siguiente es la alternativa Bot API legacy y no se usa por el
cliente MTProto:

`POST /api/telegram/webhook` solo acepta chats privados y requiere el header
`X-Telegram-Bot-Api-Secret-Token` que Telegram configura como `secret_token`.
El servidor requiere `TELEGRAM_BOT_TOKEN` y `TELEGRAM_WEBHOOK_SECRET`.

- `/start` entrega aviso de privacidad y reglas.
- `/consulta <problema>` procesa una sola consulta de hasta 500 caracteres con
  las guías locales; no invoca Hermes, no crea tickets ni persiste mensajes,
  identificadores de usuario o historial.
- Los IDs de actualización se mantienen en una caché acotada en memoria para
  deduplicar reintentos. Cada fallo al enviar la respuesta produce `503` para
  que Telegram pueda reintentar.
- Telegram procesa el texto de entrada y la respuesta. No se deben enviar
  contraseñas, códigos MFA ni datos confidenciales. El canal no reemplaza el
  flujo web consentido de escalación.