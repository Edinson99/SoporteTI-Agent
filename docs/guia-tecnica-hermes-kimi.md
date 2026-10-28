# Guia tecnica: SoporteTI-Agent con Hermes y Kimi

Esta guia documenta la integracion verificada en Windows 11 + Ubuntu/WSL2:

- Hermes Agent como redactor/orquestador en sus sesiones propias.
- El chat web de SoporteTI-Agent como interfaz personalizada que invoca Hermes
  localmente despues de generar el diagnostico estructurado.
- Kimi como proveedor del modelo por la API global de Moonshot.
- SoporteTI-Agent como servidor MCP local por stdio.
- Una herramienta de solo diagnostico que reutiliza la misma logica de la API FastAPI.

La herramienta no ejecuta comandos en los equipos, no cambia configuraciones y
no crea tickets reales. Los casos sin procedimiento conocido solicitan revision
humana. No se requiere desplegar la API FastAPI para utilizar MCP localmente.

## Arquitectura

```text
Usuario
  |
  v
Chat web -> FastAPI -> AgenteSoporteTI -> Hermes CLI -> modelo configurado
                            |           herramienta web / web + vision
                            +--> base local de conocimiento

Hermes interactivo -> MCP stdio -> SoporteTI-Agent (app.mcp_server)
  |
  +--> AgenteSoporteTI
         +--> buscar_conocimiento --> data/conocimiento_soporte.json
         +--> crear_borrador_ticket (local, no persistente)
```

La herramienta se anuncia a Hermes como
`mcp__soporte_ti__consultar_soporte_ti`. Sus argumentos son `question`,
`user_id` y `context` opcional. La respuesta usa el contrato de diagnóstico
v1.3.

## Chat web personalizado con Hermes + Kimi

El endpoint local `POST /agent/chat` conecta la interfaz personalizada sin
exponer la clave de Kimi:

1. FastAPI valida la solicitud y obtiene el diagnostico de
   `AgenteSoporteTI` y de la base de conocimiento local.
2. FastAPI inicia Hermes en WSL con la herramienta `web`; si el turno incluye
   capturas, habilita `web,vision`. No habilita terminal ni comandos. Hermes usa el proveedor
   y modelo guardados en su configuracion privada; en esta configuracion se usa
   Kimi.
3. Hermes redacta la respuesta usando la pregunta, el resultado local y hasta
   diez mensajes anteriores. Si la guia local no basta, puede buscar
   documentacion oficial; con capturas, puede leer mensajes y codigos visibles.
   `user_id` no se incluye en el prompt.
4. El navegador muestra la redaccion del modelo junto a las hipotesis, fuentes,
   evidencia y acciones estructuradas del diagnostico local.

El historial vive en la memoria de la pagina y se borra al recargar. La ruta
web no habilita terminal ni comandos. Las capturas se guardan temporalmente
durante el turno y solo se conservan en el ticket despues del consentimiento;
no se adjuntan al correo. La base local determina las guias, evidencias y pasos
antes de enviar el resultado al modelo. El transporte MCP sigue disponible
para sesiones interactivas de Hermes.

El chat formula una pregunta para que el usuario pueda continuar. Si la
incidencia sigue sin resolverse, ofrece el formulario de contacto tras tres
respuestas del usuario a partir de la consulta inicial, incluso si se encontró
una guía local; la solicitud explícita de contacto adelanta el formulario.
Admite hasta tres imágenes JPG, PNG o WebP de 2 MiB cada una; valida MIME y
firma binaria. El contenido de imagen y web se considera no confiable. La UI
solo convierte en enlaces HTTPS los dominios oficiales que tiene permitidos.

La ruta es solo loopback y requiere Hermes en WSL. Pregunta, contexto,
diagnostico local, historial y las capturas del turno se envian al proveedor
configurado mediante Hermes; no introduzcas datos confidenciales. Si Hermes o
el proveedor falla, la ruta devuelve un error `503` explicito en vez de fingir
una respuesta del modelo. El proveedor puede cambiarse desde `hermes model`;
Kimi es la configuracion recomendada descrita en esta guia.

## Requisitos y ubicacion

- Windows con WSL2 y la distribucion Ubuntu instalada.
- Hermes instalado y ejecutable como `hermes` desde Ubuntu.
- Acceso a una clave de **Kimi Open Platform API global**, con modelo/cuota
  disponibles. La cuenta del chat web no garantiza acceso a la API.
- Git, `curl`, Python 3 y soporte para entornos virtuales disponibles en Ubuntu.
- El checkout de este repositorio. En la configuracion validada estaba en
  `/mnt/c/Users/javie/OneDrive/Documents/GitHub/SoporteTI-Agent`.
- Un entorno virtual y dependencias MCP en
  `/home/javier/.venvs/soporteti-agent`.

En otra computadora o cuenta, reemplaza esas rutas por las que existan en tu
WSL. Mantener el entorno virtual en el sistema de archivos Linux evita
problemas de permisos y rendimiento asociados a OneDrive.

## 1. Instalar Hermes (si todavia no esta instalado)

Desde Ubuntu/WSL, como usuario normal, no como `root` ni con `sudo`:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes --help
hermes doctor
```

Verifica el dominio antes de ejecutar el instalador. Si Hermes ya funciona,
omite este paso.

## 2. Conectar Hermes con Kimi

En la terminal Ubuntu:

```bash
hermes model
```

Para la API global de Kimi, selecciona el proveedor Moonshot o endpoint
personalizado. Valores de referencia:

```text
Base URL: https://api.moonshot.ai/v1
API compatibility: Chat Completions
Model: uno habilitado en la cuenta (por ejemplo kimi-k2.6)
Reasoning effort: medium (opcional)
```

Si Hermes comprueba el endpoint y muestra los modelos disponibles, elige uno de
esa lista. En la configuracion validada, `kimi-k2.6` fue seleccionado, el
endpoint devolvio cuatro modelos y el contexto se detecto automaticamente en
262.1K tokens. Esos valores pueden variar por cuenta y fecha. `kimi-k2.7-code`
y `kimi-k2.7-code-highspeed` son identificadores distintos; no asumas que un
modelo de coding es intercambiable con los modelos generales.

Hermes guardo la clave en su archivo de entorno privado, con una variable
parecida a `HERMES_CUSTOM_API_MOONSHOT_AI_API_KEY`. No copies la clave a este
repositorio, al archivo `config.yaml`, a mensajes o a registros compartidos.
No combines una clave de Kimi Code con el endpoint de la API global.

Comprueba la seleccion dentro de Hermes con `/model` y `/status`.

## 3. Preparar el checkout y el entorno Python

Si todavia no clonaste el repositorio en Ubuntu:

```bash
git clone https://github.com/Edinson2499/SoporteTI-Agent.git
```

Entra al checkout existente y confirma la ruta:

```bash
cd /mnt/c/Users/javie/OneDrive/Documents/GitHub/SoporteTI-Agent
pwd
```

Crea el entorno virtual Linux e instala las dependencias del repositorio:

```bash
mkdir -p ~/.venvs
python3 -m venv ~/.venvs/soporteti-agent
~/.venvs/soporteti-agent/bin/python -m pip install --upgrade pip
~/.venvs/soporteti-agent/bin/python -m pip install -r requirements.txt
```

Si el entorno ya existe, no hace falta crearlo de nuevo. Comprueba la
instalacion del SDK y corre las pruebas:

```bash
~/.venvs/soporteti-agent/bin/python -m pip show mcp
cd /mnt/c/Users/javie/OneDrive/Documents/GitHub/SoporteTI-Agent
~/.venvs/soporteti-agent/bin/python -m pytest tests/ -q
```

En la sesion validada, las nueve pruebas pasaron con Python 3.14.4 en WSL.
Hermes invoca el proceso MCP con el interprete del entorno virtual; no necesita
que FastAPI este escuchando en un puerto.

## 4. Registrar el servidor en Hermes

La configuracion reside en Ubuntu, en `~/.hermes/config.yaml`, no en
`app/main.py` ni dentro del repositorio. Para editarla:

```bash
nano ~/.hermes/config.yaml
```

Agrega esta entrada bajo `mcp_servers:`:

```yaml
mcp_servers:
  soporte_ti:
    command: "/home/javier/.venvs/soporteti-agent/bin/python"
    args: ["-m", "app.mcp_server"]
    env:
      PYTHONPATH: "/mnt/c/Users/javie/OneDrive/Documents/GitHub/SoporteTI-Agent"
    timeout: 30
    tools:
      include: [consultar_soporte_ti]
      resources: false
      prompts: false
```

Si `mcp_servers:` ya existe, agrega solo la entrada `soporte_ti:` dentro de esa
seccion: no dupliques la clave superior. Ajusta las dos rutas a tu instalacion
de WSL. Guarda con `Ctrl+O`, confirma con `Enter` y sal con `Ctrl+X`.

## 5. Confirmar la conexion y empezar una sesion

Desde Ubuntu, fuera de una conversacion Hermes:

```bash
hermes mcp list
hermes mcp test soporte_ti
```

El estado esperado es habilitado y la prueba debe conectarse y descubrir una
herramienta llamada `consultar_soporte_ti`. Si Hermes ya estaba abierto, ejecuta
`/reload-mcp` dentro de la conversacion; si no, inicia una sesion nueva:

```bash
hermes
```

Dentro de Hermes, verifica el proveedor con `/model`. Pide un diagnostico
especificando el identificador de usuario y la incidencia, por ejemplo:

```text
Tengo un incidente: no tengo internet en mi portatil.
Usa el usuario USR-1042 y consulta la herramienta de soporte TI antes de recomendar pasos.
```

Hermes puede incluir el contexto del dispositivo si es necesario. Para un tema
reconocido, la herramienta devuelve la guia y su fuente; si no hay guia,
devuelve escalacion pendiente de aprobacion. Para cerrar Hermes, usa `Ctrl+D`.

## Diagnostico de problemas

| Sintoma | Comprobacion |
| --- | --- |
| `hermes: command not found` | En Ubuntu, ejecuta `source ~/.bashrc` o abre una terminal WSL nueva; verifica `hermes --help`. |
| Servidor no aparece en Hermes | Comprueba que `~/.hermes/config.yaml` tenga una unica seccion `mcp_servers:` y una entrada `soporte_ti:`. Ejecuta `hermes mcp list`. |
| Error al iniciar el proceso MCP | Comprueba las rutas `command` y `PYTHONPATH`, y ejecuta `~/.venvs/soporteti-agent/bin/python -m pip show mcp`. |
| No se descubre la herramienta | Ejecuta `hermes mcp test soporte_ti`; confirma `args: ["-m", "app.mcp_server"]` y `include: [consultar_soporte_ti]`. |
| Hermes no usa la herramienta | Ejecuta `/reload-mcp` o abre una sesion nueva y pide explicitamente que consulte soporte TI. |
| Error de Kimi/credencial | Ejecuta `hermes model` y revisa proveedor, endpoint, modelo habilitado, cuota y credencial en Hermes; no compartas la clave. |
| `No module named pip` en el venv | Usa un entorno virtual limpio creado con `python3 -m venv` desde Ubuntu; instala `python3-venv` si el sistema lo requiere. |

## Correo de escalacion y firma Gmail (opcional)

El envío de correo se ejecuta en la aplicación local de Windows, separado del
Hermes que corre en WSL. Los avisos incluyen una versión HTML con prioridad,
resumen del problema, contacto, contexto, conversación y firma Gmail; también
mantienen una versión de texto plano para clientes que no muestran HTML.
Configura Gmail API OAuth siguiendo las
[notas de versión 1.3.5](version-1.3.5.md). En resumen: habilita Gmail API en
Google Cloud, crea credenciales OAuth de escritorio, guarda el JSON en
`.secrets/gmail-oauth-client.json` y ejecuta desde PowerShell la autorización:

```powershell
.\.venv\Scripts\python.exe scripts\authorize_gmail.py
```

Si la pantalla OAuth está en modo de prueba, agrega la cuenta autorizada como
usuario de prueba. El remitente configurado debe ser la cuenta autorizada o un
alias habilitado. El token OAuth y el JSON de cliente son secretos locales:
no los subas a Git ni los incluyas en capturas o registros compartidos. El
ticket se persiste antes del envío y no se pierde si Gmail falla; las capturas
no se adjuntan al correo.

## Limites operativos

- MCP stdio solo funciona cuando el proceso Hermes puede ejecutar el Python y
  acceder a la ruta del proyecto.
- No expongas el proceso MCP local en una red. Para acceso remoto se necesita
  transporte HTTP seguro, autenticacion y controles de acceso.
- El borrador de ticket que devuelve el agente no se persiste ni se envia a un
  sistema externo.
- Kimi redacta la conversacion; los procedimientos autorizados y sus fuentes
  provienen del agente local y de `data/conocimiento_soporte.json`.
