# 🛠️ SoporteTI-Agent

**Un asistente de soporte TI que convierte incidencias comunes en pasos claros y seguros.**

**Version 1.3.0:** incorpora diagnostico guiado, preguntas de seguimiento y
busqueda local tolerante a acentos con varias coincidencias ordenadas.
Consulta las [notas de la version 1.3.0](docs/version-1.3.md) para el detalle
del contrato, las pruebas y los limites de esta entrega.

Describe el problema; SoporteTI-Agent busca una guía local, devuelve recomendaciones con su fuente y, cuando no encuentra una respuesta, solicita revisión humana en lugar de inventar una solución.

> **Estado actual:** el diagnóstico del backend es determinista y se basa en palabras clave y una base de conocimiento versionada. Hermes y Kimi son una integración conversacional opcional; Kimi no forma parte del backend ni es necesario para usar la API.

## ✨ ¿Qué puede hacer?

- 🔎 Buscar y ordenar varias guías coincidentes en la base de conocimiento local, normalizando mayúsculas, acentos y puntuación.
- 🧭 Entregar pasos seguros, el identificador de la guía y la siguiente acción recomendada.
- 🧑‍💻 Aceptar contexto opcional del equipo, como dispositivo y sistema operativo.
- 🧪 Proponer hipótesis provisionales y pruebas de descarte a partir de las guías y de comprobaciones de red reportadas por el usuario.
- ❓ Preguntar por sistema operativo, alcance, mensaje de error y cambios recientes cuando falten esos datos.
- 🙋 Solicitar revisión humana si no encuentra una guía; prepara un borrador temporal, no un ticket real.
- 🔌 Ofrecer la misma lógica mediante API HTTP, AWS Lambda o una herramienta MCP local para Hermes.
- ✅ Validar las solicitudes y responder con un contrato JSON consistente.

### Temas cubiertos

🌐 Conectividad e internet · 🐢 Rendimiento · 🖨️ Impresoras · ✉️ Correo · 🔐 Cuentas y MFA · 🛡️ VPN · 📦 Instalación de software · 🎧 Periféricos · 🚨 Correos sospechosos · 🪟 Errores de Windows y actualizaciones · 🔋 Batería y energía · 💾 Formateo y respaldos · 🪪 Licencias · ⌨️ Diagnóstico CMD · ⚙️ Optimización.

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

## 🔗 Formas de integración y despliegue

| Modalidad | Qué ofrece | Documentación |
| --- | --- | --- |
| **API local** | FastAPI con `GET /health` y `POST /agent/ask`. | [Contrato HTTP](docs/api-contract.md) |
| **Hermes + MCP** | Hermes puede consultar la herramienta local `consultar_soporte_ti`; Kimi puede usarse como modelo conversacional en Hermes. | [Guía técnica](docs/guia-tecnica-hermes-kimi.md) · [Guía para usuarios](docs/guia-usuario-hermes-kimi.md) |
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
4. Si faltan datos, la respuesta propone preguntas sobre sistema operativo, alcance, error y cambios recientes.
5. Si el usuario incluye `context.network_checks`, el agente interpreta esos valores como resultados declarados, sin ejecutar pruebas en su equipo.
6. Si no hay coincidencia, se devuelve un borrador de escalación temporal y `needs_approval: true`.

La API, Lambda y MCP comparten el mismo agente y la misma base de conocimiento. Consulta el [mapa de arquitectura](docs/arquitectura.md) y la [matriz de componentes y verificación](docs/reporte-matriz-v0.1.md) para más detalle.

## 🔒 Límites y seguridad

- El agente **recomienda**, pero no ejecuta comandos ni modifica el equipo; los resultados de `network_checks` no se verifican desde el servidor.
- No instala software, no cambia contraseñas y no crea ni envía tickets reales.
- Los borradores de escalación no se guardan: existen solo durante la solicitud. `incident_id` es `null`; la persistencia de tickets queda fuera de esta versión.
- La base de conocimiento está versionada localmente; el backend no consulta Kimi ni servicios externos para diagnosticar.
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
