# SoporteTI-Agent

Base tecnica v0.1 de un agente de soporte TI. Recibe una incidencia, analiza el contexto, consulta una base de conocimiento local, devuelve pasos seguros y escala los casos sin guia para aprobacion humana.

## Estructura

```
app/                 API, orquestador y herramientas
data/                conocimiento y contratos JSON
tests/               pruebas automatizadas
docs/                contrato, arquitectura, mapa y evidencia
.env.example         configuracion segura de ejemplo
.gitignore           archivos que no se versionan
```

## Arquitectura

El agente sigue el ciclo: **objetivo -> contexto -> decision -> herramientas -> observacion -> limites**. Consulta el [mapa de arquitectura](docs/arquitectura.md) y el [contrato HTTP](docs/api-contract.md).

## Integracion con Hermes y Kimi

Hermes puede usar Kimi como modelo y consultar el diagnostico de este proyecto
mediante una herramienta MCP local. La [guia de integracion Hermes + Kimi](docs/hermes-kimi.md)
describe la configuracion y las pruebas manuales. La clave API de Kimi se
configura en Hermes; no se guarda en este proyecto.

Para desplegar y mantener la conexion, consulta la
[guia tecnica Hermes + Kimi](docs/guia-tecnica-hermes-kimi.md). Para iniciar
Hermes y pedir ayuda con una incidencia, consulta la
[guia para usuarios](docs/guia-usuario-hermes-kimi.md).

## Entorno aislado y ejecucion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest tests/ -v
uvicorn app.main:app --reload
```

La API queda en `http://127.0.0.1:8000` y la documentacion interactiva en `http://127.0.0.1:8000/docs`.

## Despliegue en AWS Lambda

El proyecto incluye [template.yaml](template.yaml) para AWS SAM. La funcion usa el handler `app.lambda_handler.handler`, incluye la base de conocimiento local y expone una API HTTP con `GET /health` y `POST /agent/ask`.

Requiere AWS CLI, AWS SAM CLI, credenciales configuradas y Python 3.12 para coincidir con el runtime:

```powershell
aws configure
.\scripts\deploy.ps1 -StackName soporte-ti-agent-dev -Region us-east-1
```

El script ejecuta `sam build`, despliega el stack y muestra la URL de la API. Para probarla:

```powershell
$apiUrl = "https://<api-id>.execute-api.us-east-1.amazonaws.com"
Invoke-RestMethod "$apiUrl/health"
Invoke-RestMethod "$apiUrl/agent/ask" -Method Post -ContentType "application/json" -Body (@{
  question = "No tengo internet en mi portatil"
  user_id = "USR-1042"
  context = @{ device = "portatil" }
} | ConvertTo-Json)
```

## Despliegue en AWS Lambda (agente soporte IT)

La funcion `agentesoporit-lambda-v01` (region `us-east-2`) corre el handler `lambda_function.lambda_handler`
en `python3.13`. El codigo esta versionado en [lambda/agentesoporit-lambda-v01](lambda/agentesoporit-lambda-v01),
valida `request_id`, `user_id`, `question`, `channel` y responde `status`, `answer`, `source`, `next_action`.

## Despliegue en EC2 (Amazon Linux 2023)

El proyecto tambien corre como servicio persistente (`systemd`) en una instancia EC2, sirviendo el mismo FastAPI
de `app/main.py` con `uvicorn` en el puerto `8000`.

```bash
sudo dnf install -y python3.11 python3.11-pip git
git clone https://github.com/Edinson2499/SoporteTI-Agent.git
cd SoporteTI-Agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt uvicorn
```

Servicio `systemd` (`/etc/systemd/system/soporteti-agent.service`) para que quede activo tras reinicios o cierre de sesion:

```ini
[Unit]
Description=SoporteTI-Agent FastAPI
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/SoporteTI-Agent
ExecStart=/home/ec2-user/SoporteTI-Agent/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now soporteti-agent
```

Requiere una regla de entrada en el Security Group (Custom TCP, puerto `8000`, origen `0.0.0.0/0`). La IP publica
de la instancia cambia si se reinicia sin una Elastic IP asociada.

## Guia rapida: clonar y ejecutar en cualquier equipo (PowerShell)

Requiere Python 3.11+ y Git instalados y disponibles en el `PATH`.

```powershell
# 1. Clonar el repositorio
git clone https://github.com/<usuario>/SoporteTI-Agent.git
cd SoporteTI-Agent

# 2. Configurar entorno (venv + dependencias + .env + pruebas)
.\scripts\setup.ps1

# 3. Iniciar la API
.\scripts\start.ps1
```

- `setup.ps1` detecta Python 3.11+ mediante `python` o el lanzador `py`, crea `.venv`, instala `requirements.txt`, genera `.env` desde `.env.example` (si no existe) y corre `pytest`. Usa `-SkipTests` para omitir las pruebas.
- `start.ps1` activa el entorno virtual y levanta `uvicorn` en `http://127.0.0.1:8000` (usa `-Port` para cambiar el puerto).
- Si PowerShell bloquea la ejecucion de scripts, corre una vez: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- Para ejecutar solo las pruebas despues de configurar el entorno: `.\.venv\Scripts\python.exe -m pytest tests/ -v`.

Pasos manuales equivalentes (sin los scripts):

```powershell
git clone https://github.com/<usuario>/SoporteTI-Agent.git
cd SoporteTI-Agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest tests/ -v
uvicorn app.main:app --reload
```

## Ejemplo

```http
POST /agent/ask
Content-Type: application/json

{
  "question": "No tengo internet en mi portatil",
  "user_id": "USR-1042",
  "context": {
    "device": "portatil",
    "operating_system": "Windows 11"
  }
}
```

Los contratos de referencia estan en [data/agent_request.json](data/agent_request.json) y [data/agent_response.json](data/agent_response.json). La base de conocimiento local esta en [data/conocimiento_soporte.json](data/conocimiento_soporte.json).

## Limites

El agente no ejecuta comandos administrativos, no instala software, no cambia contrasenas, no modifica configuraciones criticas, no elimina archivos y no envia tickets. Cuando no encuentra una guia, prepara un borrador y devuelve `needs_approval: true`.

## Evidencia

La [matriz de la base tecnica](docs/reporte-matriz-v0.1.md) resume componentes, responsabilidades y pruebas. Usa `git status`, `git log --oneline` y `git push` para registrar decisiones pequenas y verificables.