# Integracion con Hermes Agent y Kimi

Hermes coordina la conversacion, Kimi es el modelo de lenguaje y este proyecto
expone el diagnostico existente como una herramienta MCP local. La clave de Kimi
se configura solamente en Hermes; no se envia a SoporteTI-Agent ni se guarda en
este repositorio.

Esta guia cubre la integracion MCP interactiva. El chat web local es otra
superficie: desde la version 1.3.7 puede usar web y vision de Hermes, hace
aclaraciones y conserva capturas en tickets autorizados. Revisa la
[guia tecnica actualizada](guia-tecnica-hermes-kimi.md) y las
[notas 1.3.7](version-1.3.7.md) para ese flujo. La API Gmail y el panel local
se documentan en las [notas 1.3.5](version-1.3.5.md) y
[notas 1.3.6](version-1.3.6.md).

## 1. Preparar Hermes y Kimi

La ruta recomendada es Hermes en Ubuntu/WSL2 y la API global de Kimi. Sigue la
guia del laboratorio para instalar Hermes desde su fuente oficial. En Ubuntu,
el instalador y las comprobaciones son:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes --help
hermes doctor
```

Ejecuta el instalador como tu usuario normal, no con `sudo`, y verifica que el
dominio sea el oficial. Luego crea una clave API global en Kimi Open Platform;
el chat web de Kimi por si solo no habilita el acceso a la API.

En la terminal de Ubuntu, configura el proveedor:

```bash
hermes model
```

Selecciona Kimi/Moonshot o un endpoint personalizado con estos valores:

```text
Base URL: https://api.moonshot.ai/v1
Model: kimi-k3
Transport: chat_completions
```

El modelo disponible depende de la cuenta. Si `kimi-k3` no esta habilitado,
selecciona un modelo compatible con herramientas que tu cuenta permita. La API
global de Kimi y Kimi Code usan credenciales y endpoints diferentes; no
intercambies sus claves ni sus identificadores de modelo.

## 2. Instalar el servidor de soporte

Clona este repositorio dentro del sistema de archivos Linux de WSL2 y prepara
sus dependencias:

```bash
git clone https://github.com/Edinson2499/SoporteTI-Agent.git
cd SoporteTI-Agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No es necesario iniciar FastAPI para la conexion MCP local. Hermes inicia el
servidor MCP por stdio cuando necesita llamar la herramienta.

## 3. Registrar la herramienta MCP en Hermes

Abre `~/.hermes/config.yaml` en Ubuntu y agrega el bloque siguiente bajo
`mcp_servers:`. Si ya existe esa seccion, agrega solo la entrada
`soporte_ti` dentro de ella. Sustituye `/home/USUARIO/SoporteTI-Agent` por la
ruta real del clon (compruebala con `pwd`):

```yaml
mcp_servers:
  soporte_ti:
    command: "/home/USUARIO/SoporteTI-Agent/.venv/bin/python"
    args: ["-m", "app.mcp_server"]
    env:
      PYTHONPATH: "/home/USUARIO/SoporteTI-Agent"
    timeout: 30
    tools:
      include: [consultar_soporte_ti]
      resources: false
      prompts: false
```

Guarda el archivo y reinicia Hermes o ejecuta `/reload-mcp` en una conversacion
activa. La herramienta se presentara como
`mcp__soporte_ti__consultar_soporte_ti`.

## 4. Probar el flujo

Inicia Hermes y solicita, por ejemplo:

```text
Ayudame con este incidente: no tengo internet en mi portatil.
Usa el usuario USR-1042 y el contexto device=portatil, operating_system=Windows 11.
Consulta la herramienta de soporte antes de recomendar pasos.
```

Hermes debe invocar la herramienta y basar su respuesta en el resultado. La
herramienta valida `question` (5-500 caracteres) y `user_id` (3-50 caracteres)
con el mismo contrato de la API FastAPI. Devuelve `answer`, `sources`,
`needs_approval` y `next_action`. Los casos sin guia requieren aprobacion humana;
no se ejecutan comandos ni se crean tickets reales.

Para revisar la configuracion de Kimi en Hermes usa `/model` y `/status`. No
copies claves API en esta conversacion, en el codigo, en `config.yaml` ni en
registros compartidos. Hermes gestiona la credencial de Kimi por separado.

## Limitaciones

- El transporte stdio requiere que Hermes y el proyecto esten disponibles en el
  mismo entorno donde Hermes puede ejecutar el interprete Python del proyecto.
- Esta integracion MCP es local. Para que un Hermes remoto o un equipo distinto
  alcance el servicio, se requiere desplegar un servidor MCP remoto con
  autenticacion y transporte HTTP seguro; no expongas el servidor local sin esa
  proteccion.
- Kimi puede redactar la explicacion conversacional, pero el diagnostico
  autorizado y sus fuentes provienen de la herramienta de este proyecto.
