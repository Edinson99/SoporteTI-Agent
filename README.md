# 🛠️ SoporteTI-Agent

**Un asistente de soporte TI que convierte incidencias comunes en pasos claros y seguros.**

**Versión actual: 1.3.7.** El chat puede hacer preguntas de seguimiento,
consultar documentación oficial y analizar capturas antes de escalar un caso.
La versión 1.3.5 incorporó el envío por Gmail API con la firma configurada en
Gmail; la 1.3.6 mejoró la gestión local de tickets. Consulta las
[notas 1.3.7](docs/version-1.3.7.md), las
[notas 1.3.6](docs/version-1.3.6.md), las
[notas 1.3.5](docs/version-1.3.5.md), las
[notas 1.3.4](docs/version-1.3.4.md),
[notas 1.3.3](docs/version-1.3.3.md), las
[notas 1.3.2](docs/version-1.3.2.md), las
[notas 1.3.1](docs/version-1.3.1.md) y las
[notas 1.3.0](docs/version-1.3.md).

Describe el problema; SoporteTI-Agent busca una guía local, devuelve recomendaciones con su fuente y, cuando no encuentra una respuesta, solicita revisión humana en lugar de inventar una solución.

> **Estado actual:** el diagnóstico local es determinista y se basa en palabras clave y una base de conocimiento versionada. El chat web usa el Hermes CLI instalado localmente para redactar respuestas con el modelo configurado en Hermes; la API de diagnóstico local sigue disponible sin Hermes.

## ✨ ¿Qué puede hacer?

- 🔎 Buscar y ordenar varias guías coincidentes en la base de conocimiento local, normalizando mayúsculas, acentos y puntuación.
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

### Temas cubiertos

🌐 Conectividad, DNS y rutas · 🐢 Rendimiento · 🖨️ Impresoras y proyectores · ✉️ Correo en PC y móvil · 🔐 Cuentas y MFA · 🛡️ VPN y phishing · 📦 Instalación de software · 🎧 Periféricos y videollamadas · 🪟 Errores de Windows, GPO y GPU · 💾 Recuperación y respaldos · 🪪 Licencias y firma digital · ⌨️ Diagnóstico CMD · 📚 Moodle y Canvas · 📊 Excel, ERP y exportaciones · 🐳 Docker, VS Code y puertos.

Las guías de diagnóstico avanzado priorizan comprobaciones de solo lectura y
escalamiento. No recomiendan desactivar controles de seguridad, modificar
particiones o firmware, abrir equipos ni terminar procesos sin autorización.

La búsqueda sigue siendo determinista por palabras completas; no es semántica ni RAG. La confianza expresa relevancia heurística de una coincidencia, no certeza de causa raíz.

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
- **Estado del servicio:** `http://127.0.0.1:8000/health`

Para omitir las pruebas durante la instalación, usa `.\scripts\setup.ps1 -SkipTests`. Para elegir otro puerto, inicia con `.\scripts\start.ps1 -Port 8080`.

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
- El ticket conserva la conversación, el texto de la consulta y los datos de contacto en el backend seleccionado. Protege la base SQLite o el proyecto Firebase y no incluyas credenciales ni datos confidenciales en el chat.
- El panel de seguimiento contiene datos personales y solo está protegido por acceso loopback; úsalo únicamente en un equipo local de confianza. No ofrece autenticación de técnicos.
- La base de conocimiento está versionada localmente. El diagnóstico estructurado no consulta servicios externos; la búsqueda web solo está disponible en el chat Hermes.
- El chat web envía la pregunta, el resultado local de diagnóstico y hasta diez turnos previos al modelo configurado en Hermes. El historial vive solo en la memoria de la página y se pierde al recargar.
- Hermes puede usar la búsqueda web acotada; cuando hay capturas también se activa visión. La ruta web no habilita terminal ni ejecución de comandos.
- La pregunta, el contexto, el historial y las capturas del turno se envían al proveedor configurado mediante Hermes. No incluyas información confidencial en el chat ni en las capturas.
- Las imágenes se conservan en el ticket solo después del consentimiento para escalar el caso; se muestran en el panel local y no se adjuntan al correo.
- La búsqueda no es semántica y las cifras de confianza no están calibradas clínicamente ni estadísticamente; expresan solo la fuerza relativa de la coincidencia.
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
