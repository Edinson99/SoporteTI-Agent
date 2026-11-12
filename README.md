# 🛠️ SoporteTI-Agent

**Un asistente de soporte TI que convierte incidencias comunes en pasos claros y seguros.**

**Versión actual: 1.4.0.** El chat responde en español sin tildes ni `ñ`,
puede hacer preguntas de seguimiento, consultar documentación oficial y analizar
capturas antes de escalar un caso. La búsqueda semántica local es opcional y
complementa la búsqueda por palabras clave sin enviar consultas a un proveedor
de embeddings. El chat permite valorar guías y guarda localmente solo la guía,
el voto y la fecha por un máximo de 180 días. Las etapas 2–5 de la fase de
mejora incorporan observabilidad filtrada, notificaciones resilientes,
Telegram de una sola consulta, ciclo de vida de capturas y estado del servicio.
Consulta las
[notas 1.4.0](docs/version-1.4.0.md),
[notas 1.3.13](docs/version-1.3.13.md),
[notas 1.3.12](docs/version-1.3.12.md),
[notas 1.3.11](docs/version-1.3.11.md),
[notas 1.3.10](docs/version-1.3.10.md), las
[notas 1.3.9](docs/version-1.3.9.md), las
[notas 1.3.8](docs/version-1.3.8.md), las
[notas 1.3.7](docs/version-1.3.7.md), las
[notas 1.3.6](docs/version-1.3.6.md), las
[notas 1.3.5](docs/version-1.3.5.md), las
[notas 1.3.4](docs/version-1.3.4.md),
[notas 1.3.3](docs/version-1.3.3.md), las
[notas 1.3.2](docs/version-1.3.2.md), las
[notas 1.3.1](docs/version-1.3.1.md) y las
[notas 1.3.0](docs/version-1.3.md).

> **Fase de mejora:** las versiones 1.3.9 y 1.3.10 añaden recuperación
> semántica opcional y su benchmark; la 1.3.11 incorpora feedback mínimo local;
> la 1.3.12 mejora consultas sobre macros de Excel y la 1.3.13 amplía la
> recuperación de paráfrasis. La 1.4.0 completa las etapas 2–5. La aprobación
> de conocimiento derivado de tickets sigue pendiente en la
> [hoja de ruta](docs/fase-mejora.md). Los resultados y pendientes de las
> pruebas reales están en el [informe de integraciones](docs/validacion-integraciones-2026-11-11.md).

Describe el problema; SoporteTI-Agent busca una guía local, devuelve recomendaciones con su fuente y, cuando no encuentra una respuesta, solicita revisión humana en lugar de inventar una solución.

> **Estado actual:** el diagnóstico local usa por defecto palabras clave y una base de conocimiento versionada; la búsqueda semántica local puede habilitarse por separado. El chat web usa el Hermes CLI instalado localmente para redactar respuestas con el modelo configurado en Hermes; la API de diagnóstico local sigue disponible sin Hermes.

## ✨ ¿Qué puede hacer?

- 🔎 Buscar y ordenar varias guías coincidentes en la base de conocimiento local, normalizando mayúsculas, acentos y puntuación.
- 🧠 Añadir recuperación semántica local opcional mediante embeddings multilingües, conservando el respaldo léxico.
- 👍 Valorar la utilidad de una guía sin guardar la pregunta, conversación ni identidad del usuario.
- 📈 Medir solicitudes, errores y latencias agregadas en memoria; limitar solicitudes y, si se configura, enviar eventos depurados a Sentry.
- 🧭 Entregar pasos seguros, el identificador de la guía y la siguiente acción recomendada.
- 🧑‍💻 Aceptar contexto opcional del equipo, como dispositivo y sistema operativo.
- 🧪 Proponer hipótesis provisionales y pruebas de descarte a partir de las guías y de comprobaciones de red reportadas por el usuario.
- ❓ Preguntar por sistema operativo, alcance, mensaje de error y cambios recientes cuando falten esos datos.
- 🖼️ Analizar hasta tres capturas de pantalla y leer códigos de error visibles.
- 🌐 Consultar documentación oficial en la web cuando las guías locales no basten.
- 🙋 Pedir nombre, correo y teléfono antes de crear y notificar un ticket sin guía o sin solución tras el seguimiento.
- 📋 Permitir al técnico revisar tickets locales, registrar una nota y marcarlos resueltos.
- 🔌 Ofrecer diagnóstico local mediante API HTTP, AWS Lambda o MCP; el chat web puede redactar la respuesta mediante Hermes y el modelo configurado en la estación.
- ✅ Validar las solicitudes y responder con un contrato JSON consistente.
- ✉️ Enviar correos de ticket por Gmail con respaldo opcional de Resend, estados de entrega y alerta Slack mínima para prioridad alta.
- 📱 Atender una consulta por Telegram con guías locales, sin guardar mensajes ni historial.
- 🟢 Mostrar el estado de la API y la configuración de dependencias en una página que no bloquea el soporte.

### Temas cubiertos

🌐 Conectividad, DNS y rutas · 🐢 Rendimiento · 🖨️ Impresoras y proyectores · ✉️ Correo en PC y móvil · 🔐 Cuentas y MFA · 🛡️ VPN y phishing · 📦 Instalación de software · 🎧 Periféricos y videollamadas · 🪟 Errores de Windows, GPO y GPU · 💾 Recuperación y respaldos · 🪪 Licencias y firma digital · ⌨️ Diagnóstico CMD · 📚 Moodle y Canvas · 📊 Excel, ERP y exportaciones · 🐳 Docker, VS Code y puertos.

Las guías de diagnóstico avanzado priorizan comprobaciones de solo lectura y
escalamiento. No recomiendan desactivar controles de seguridad, modificar
particiones o firmware, abrir equipos ni terminar procesos sin autorización.

La búsqueda por palabras completas sigue activa. Si se habilita la búsqueda
semántica, los embeddings multilingües se ejecutan localmente y sus resultados
se combinan con los léxicos; el umbral inicial provisional es `0.65` y requiere
evaluación con consultas representativas. La
confianza expresa relevancia heurística, no certeza de causa raíz.

## 🚀 Inicio rápido en Windows

Requiere **Python 3.11 o superior** y Git.

```powershell
git clone https://github.com/Edinson99/SoporteTI-Agent.git
cd SoporteTI-Agent
.\scripts\setup.ps1
.\scripts\start.ps1
```

El script de configuración crea el entorno virtual, instala las dependencias y ejecuta las pruebas. La API queda disponible en:

- **Interfaz gráfica del agente:** `http://127.0.0.1:8000`
- **API:** `http://127.0.0.1:8000/agent/ask`
- **Documentación interactiva:** `http://127.0.0.1:8000/docs`
- **Estado del servicio:** `http://127.0.0.1:8000/status`
- **Health check de vida:** `http://127.0.0.1:8000/health`

Para omitir las pruebas durante la instalación, usa `.\scripts\setup.ps1 -SkipTests`. Para elegir otro puerto, inicia con `.\scripts\start.ps1 -Port 8080`.

La búsqueda semántica está desactivada por defecto. Para habilitarla, instala
la dependencia local opcional y configura `SOPORTE_SEMANTIC_SEARCH=true` en
`.env`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-semantic.txt
```

El modelo se descarga en el primer uso, por lo que ese primer inicio necesita
acceso a Internet. Las preguntas y guías se procesan localmente después de
descargarlo. Si no se puede inicializar el modelo, el error se informa y no se
sustituye silenciosamente por una respuesta semántica vacía. La dependencia
opcional se mantiene fuera de `requirements.txt` para no ampliar el paquete de
AWS Lambda; los despliegues Lambda siguen usando búsqueda léxica.

Para medir la recuperación antes de habilitarla en un entorno real, ejecuta el
benchmark de consultas sintéticas (requiere la dependencia y el modelo local):

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py
```

El informe separa consultas léxicas, paráfrasis y casos sin guía; revisa también
las discrepancias antes de cambiar el umbral.

El chat muestra una valoración opcional en las respuestas que utilizan una
guía local. Solo se conserva el identificador de la guía, el voto y la fecha
UTC, con eliminación automática después de 180 días. No se guardan preguntas,
conversaciones, usuario ni datos de contacto. Los conteos agregados se pueden
consultar localmente en `GET /api/feedback/summary`; la ruta está restringida
a loopback. La base está en `data/feedback.sqlite3` por defecto y se puede
reubicar con `SOPORTE_FEEDBACK_DB`.

## 📊 Observabilidad, avisos y Telegram (opcionales)

El límite de uso predeterminado es 60 solicitudes por minuto y ruta/origen de
conexión. Cambia `SOPORTE_RATE_LIMIT_PER_MINUTE` en `.env`; el contador de
latencia, errores y solicitudes vive solo en memoria y `GET /api/metrics`
requiere loopback. No se guardan IP, preguntas, conversaciones, imágenes ni
datos de contacto en estas métricas. El límite es por proceso y no coordina
instancias distribuidas.

Para enviar excepciones a Sentry instala
`.\.venv\Scripts\python.exe -m pip install -r requirements-observability.txt`
y configura `SENTRY_DSN`. Se omiten cuerpos, URL, identidad, mensajes de error,
variables locales y breadcrumbs antes del envío; permanecen solo tipo de
excepción y marcos mínimos. Sentry no se habilita sin DSN.

Gmail sigue siendo el correo principal; si falla o no está configurado, Resend
puede actuar como respaldo con `RESEND_API_KEY`, `RESEND_FROM` y
`RESEND_TO_EMAIL`. Configura `SLACK_WEBHOOK_URL` para alertas de tickets
`high`/`critical`: Slack recibe solo número, categoría y prioridad. El panel
muestra el proveedor y estado final, incluida la clasificación
`configuration`/`transient` de fallos de correo.

El canal MTProto de cuenta personal se ejecuta como proceso separado y solo
responde a `/start` y `/consulta <problema>` en chats privados de IDs incluidos
en `TELEGRAM_MTPROTO_ALLOWED_USER_IDS`. No crea tickets ni conserva mensajes o
historial. Instala `requirements-telegram-mtproto.txt`, configura
`TELEGRAM_MTPROTO_API_ID`, `TELEGRAM_MTPROTO_API_HASH` y la lista de IDs en el `.env` local. Instala la
dependencia opcional y ejecuta:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-telegram-mtproto.txt
.\.venv\Scripts\python.exe -m scripts.telegram_mtproto
```

En el primer inicio, Telethon solicita el teléfono, el código de Telegram y,
si está habilitada, la contraseña 2FA directamente en la consola. La sesión
autenticada se guarda en `.secrets/telegram-mtproto.session`; protégela como
una credencial con acceso a la cuenta. No compartas la sesión ni registres
mensajes. La alternativa legacy de Bot API sigue disponible como webhook HTTPS
si se configura por separado con `TELEGRAM_BOT_TOKEN` y
`TELEGRAM_WEBHOOK_SECRET`.

## 💬 Cómo usarlo

Envía una incidencia a `POST /agent/ask`:

```json
{
  "question": "No tengo internet en mi portátil",
  "user_id": "USR-1042",
  "context": {
    "device": "portátil",
    "operating_system": "Windows 11"
  }
}
```

Una respuesta con guía incluye los pasos, su fuente y si necesita aprobación:

```json
{
  "answer": "Para portátil: ...",
  "sources": ["kb_internet_001"],
  "needs_approval": false,
  "next_action": "recopilar_datos",
  "incident_id": null,
  "category": "redes",
  "priority": "normal",
  "diagnosis": {
    "summary": "La descripcion coincide con un problema de conectividad de red o Internet. La causa raiz aun no esta confirmada.",
    "hypotheses": [],
    "tests": []
  },
  "evidence": ["Palabra clave coincidente: internet"],
  "confidence": 0.59,
  "recommended_actions": ["Verifica si otro dispositivo puede conectarse a la misma red."],
  "escalation_reason": null,
  "follow_up_questions": ["¿Que sistema operativo y version utilizas?"]
}
```

La solicitud requiere `question` (5–500 caracteres) y `user_id` (3–50 caracteres); `context` es opcional. El contrato completo está en [docs/api-contract.md](docs/api-contract.md), y hay ejemplos en [data/agent_request.json](data/agent_request.json) y [data/agent_response.json](data/agent_response.json).

En la interfaz web, abre **Datos para afinar el diagnóstico (opcional)** para
indicar el sistema operativo, el alcance, el mensaje o código de error y los
cambios recientes. También puedes adjuntar hasta tres capturas JPG, PNG o WebP
(máximo 2 MiB cada una). Oculta antes cualquier dato personal o confidencial.
El agente hará una pregunta concreta para continuar. Si no encuentra guía,
después de tres respuestas tuyas tras la consulta inicial ofrece el formulario
para contactar al técnico; puedes solicitarlo antes. El correo al técnico usa
un diseño HTML más claro con prioridad, contacto, contexto y conversación, y
mantiene la firma de Gmail.

El chat web envía la incidencia, el contexto y el diagnóstico local al Hermes
CLI de WSL, que utiliza el proveedor/modelo configurado en Hermes para redactar
la respuesta. En la configuración recomendada, ese modelo es Kimi, pero Hermes
puede usar otro proveedor compatible. Hermes debe estar instalado y
autenticado en WSL. Las credenciales permanecen en Hermes y no se envían al
navegador. Si Hermes o el proveedor configurado no están disponibles, el chat
muestra un error explícito en lugar de fingir una respuesta. El endpoint
determinista `POST /agent/ask` sigue disponible para clientes que no requieren
el modelo.

Cuando no hay una guía suficiente, Hermes puede buscar documentación oficial
con enlaces y redactar pasos seguros; las capturas se analizan con la
herramienta de visión. Si después de tres respuestas tuyas la incidencia sigue
sin resolverse, el chat ofrece contactar al técnico aunque hubiera encontrado
una guía.
Solo tras marcar la autorización y enviar nombre, correo y teléfono se guarda
un ticket y se intenta notificarlo; el correo incluye al usuario en copia y
usa la firma configurada en Gmail cuando Gmail API OAuth está autorizado. En
SQLite el número tiene formato
`STI-AAAAMMDD-######`; en Firebase, `STI-AAAAMMDD-<UUID>`. El seguimiento está
en `http://127.0.0.1:8000/tickets`; allí se puede anotar la solución y marcar el
caso resuelto. El panel incluye búsqueda, filtros por estado, resumen de casos,
diagnóstico y conversación. Configura Gmail API OAuth para enviar con la firma
que ya tienes en Gmail; consulta [las notas 1.3.5](docs/version-1.3.5.md).

### Persistencia Firebase Data Connect (opcional)

SQLite sigue siendo el backend predeterminado. Para guardar tickets en la
instancia Data Connect ya configurada, instala Node.js LTS, instala las
dependencias del puente y la CLI de Firebase, e inicia ADC con Google Cloud
CLI. En Windows usa los comandos `.cmd` para evitar la política que bloquea
`npm.ps1`:

```powershell
npm.cmd ci
npm.cmd install -g firebase-tools
firebase.cmd login
gcloud auth application-default login
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

En `.env`, configura `SOPORTE_TICKETS_BACKEND=firebase`,
`FIREBASE_PROJECT_ID=soporteit-tickets`,
`DATA_CONNECT_SERVICE_ID=soporteit-tickets-service` y
`DATA_CONNECT_LOCATION=us-east4`. Puedes omitir estos tres últimos valores
porque coinciden con los valores predeterminados del conector. Si Node.js no
está en `PATH`, configura `NODE_BIN` con la ruta completa a `node.exe`.
La identidad ADC debe tener permisos para invocar Data Connect en el proyecto;
`firebase login` por sí solo autentica la CLI, no el proceso de la aplicación.
No descargues ni guardes claves de cuentas de servicio en el repositorio.

Valida las operaciones y el conector local antes de iniciar la app:

```powershell
npm.cmd run dataconnect:compile
.\.venv\Scripts\python.exe -m pytest tests\test_dataconnect_tickets.py tests\test_tickets.py -v
.\scripts\start.ps1
```

El backend Firebase persiste tickets, mensajes de conversación y auditoría en
las tablas existentes de Cloud SQL a través de Data Connect. No ejecuta
migraciones SQL ni importa tickets SQLite. La creación del ticket y sus
mensajes/auditoría es transaccional; el correo se envía después de guardar y su
estado queda registrado. El número de ticket Firebase es determinista a partir
del UUID de solicitud para que un reintento no cree otro ticket.

La aplicación local ejecuta un puente Node con Firebase Admin SDK y ADC. Este
backend está pensado para un equipo o servidor de confianza; el panel solo
comprueba loopback y no autentica técnicos. No cambies el backend a Firebase
en un despliegue Lambda/SAM: esa plantilla no empaqueta el puente Node ni
configura su identidad de workload. El endpoint `/health` comprueba la API,
no la disponibilidad de Firebase.

## 🔗 Formas de integración y despliegue

| Modalidad | Qué ofrece | Documentación |
| --- | --- | --- |
| **Chat local + Hermes** | `POST /agent/chat` obtiene el diagnóstico local; Hermes redacta la respuesta, puede buscar documentación web oficial y habilita visión al recibir capturas. No tiene terminal y solo acepta loopback. | [Guía técnica](docs/guia-tecnica-hermes-kimi.md) |
| **API de diagnóstico local** | FastAPI expone `GET /health` y `POST /agent/ask`, sin invocar un LLM. | [Contrato HTTP](docs/api-contract.md) |
| **Hermes + MCP** | Hermes puede consultar la herramienta local `consultar_soporte_ti` en sesiones propias. | [Guía técnica](docs/guia-tecnica-hermes-kimi.md) · [Guía para usuarios](docs/guia-usuario-hermes-kimi.md) |
| **AWS Lambda + API Gateway** | Despliegue con AWS SAM y los mismos endpoints HTTP. | [template.yaml](template.yaml) |
| **Docker en AWS EC2** | Contenedor Python + Node.js, con SQLite persistente y credenciales fuera de la imagen. | [Guía Docker y EC2](docs/docker-ec2.md) |

Para desplegar en AWS desde PowerShell, configura AWS CLI y SAM CLI y ejecuta:

```powershell
aws configure
.\scripts\deploy.ps1 -StackName soporte-ti-agent-dev -Region us-east-1
```

El script construye y despliega el stack, y muestra la URL de la API al finalizar. **La API desplegada por esta plantilla no incluye autenticación**: no la expongas en producción o en redes públicas sin añadir autenticación, autorización y controles de uso.

## 🧠 Qué ocurre con una solicitud

1. Se validan la pregunta, el identificador de usuario y el contexto opcional.
2. Se buscan coincidencias completas normalizadas en [data/conocimiento_soporte.json](data/conocimiento_soporte.json); los artículos se cargan una vez y las coincidencias se ordenan por puntuación heurística.
3. Si hay una guía, se devuelven hasta tres fuentes, hipótesis provisionales, evidencias textuales y pasos recomendados.
4. Si faltan datos, el chat puede recabar hasta dos aclaraciones antes de ofrecer escalar el caso; una petición directa de contactar al técnico adelanta el formulario.
5. Si el usuario incluye `context.network_checks`, el agente interpreta esos valores como resultados declarados, sin ejecutar pruebas en su equipo.
6. Si no hay coincidencia suficiente, Hermes puede buscar documentación oficial y analizar capturas adjuntas. El ticket y el correo solo se crean después de que el usuario comparte sus datos y autoriza la escalación.

La API, Lambda, MCP y el chat web comparten la lógica determinista de diagnóstico. La persistencia de tickets, el correo Gmail y el panel se aplican al servidor HTTP local, no a Lambda ni a MCP. El chat usa Hermes para redactar y, según el caso, consultar la web y leer capturas; no habilita terminal ni ejecución de comandos. Consulta el [mapa de arquitectura](docs/arquitectura.md), el [contrato actual de API](docs/api-contract.md) y la [matriz histórica v0.1](docs/reporte-matriz-v0.1.md).

## 🔒 Límites y seguridad

- El agente **recomienda**, pero no ejecuta comandos ni modifica el equipo; los resultados de `network_checks` no se verifican desde el servidor.
- No instala software ni cambia contraseñas. Los tickets solo se crean cuando no hay guía y se guardan en SQLite (predeterminado) o, si se configura, en Firebase Data Connect; no se envían a una mesa de servicio externa.
- El correo requiere credenciales OAuth de Gmail API guardadas localmente en `.secrets/`; no deben incluirse en el repositorio.
- Las claves Resend, el webhook Slack y las credenciales MTProto/sesión Telegram deben permanecer en el entorno local y `.secrets/`, nunca en el repositorio. La cuenta personal solo responde a IDs permitidos. Slack recibe únicamente identificador de ticket, prioridad y categoría; el correo de respaldo transmite el contenido y contacto autorizados por el usuario a Resend.
- Los eventos Sentry no contienen contenido de solicitudes. Las métricas locales son en memoria; no son un sistema distribuido de telemetría.
- El ticket conserva la conversación, el texto de la consulta y los datos de contacto en el backend seleccionado. Protege la base SQLite o el proyecto Firebase y no incluyas credenciales ni datos confidenciales en el chat.
- El panel de seguimiento contiene datos personales y solo está protegido por acceso loopback; úsalo únicamente en un equipo local de confianza. No ofrece autenticación de técnicos.
- La base de conocimiento está versionada localmente. El diagnóstico estructurado no consulta servicios externos; la búsqueda web solo está disponible en el chat Hermes.
- El chat web envía la pregunta, el resultado local de diagnóstico y hasta diez turnos previos al modelo configurado en Hermes. El historial vive solo en la memoria de la página y se pierde al recargar.
- Hermes puede usar la búsqueda web acotada; cuando hay capturas también se activa visión. La ruta web no habilita terminal ni ejecución de comandos.
- La pregunta, el contexto, el historial y las capturas del turno se envían al proveedor configurado mediante Hermes. No incluyas información confidencial en el chat ni en las capturas.
- Las imágenes se conservan en el almacenamiento privado de tickets solo después del consentimiento; no se adjuntan a correos ni avisos Slack. Se eliminan al resolver el ticket o al cumplir 180 días (limpieza al consultar tickets/adjuntos).
- La búsqueda semántica es opcional; las cifras de confianza no están calibradas estadísticamente y expresan solo relevancia heurística.
- No incluyas contraseñas, códigos de verificación, claves API ni información confidencial en las solicitudes.
- La API no implementa autenticación. Protege el acceso antes de cualquier despliegue accesible por otras personas.

## 🧪 Pruebas

Con el entorno configurado, ejecuta:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

## 📁 Estructura del proyecto

```text
app/       API, agente compartido, herramientas y servidor MCP
data/      Base de conocimiento y ejemplos del contrato JSON
docs/      Contratos, arquitectura y guías de uso e integración
scripts/   Configuración, inicio y despliegue con AWS SAM
tests/     Pruebas automatizadas
```
