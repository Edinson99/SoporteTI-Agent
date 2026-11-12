# Docker y despliegue en AWS EC2

El contenedor ejecuta FastAPI con Python 3.11 y Node.js 20. Node se necesita
para el puente de Firebase Data Connect. El backend de tickets sigue siendo
SQLite por defecto; los datos de `data/` sobreviven a la reconstrucción de la
imagen mediante un montaje de directorio.

## Antes de publicar el servicio

- La API no implementa autenticación. Para una prueba, restringe el puerto 80
  en el Security Group a tu IP. Antes de permitir tráfico público, pon delante
  un proxy o balanceador con HTTPS y autenticación/autorización.
- `/tickets` solo permite clientes loopback y no autentica técnicos. No abras
  ese panel a Internet; el mapeo Docker del puerto no cambia esa restricción.
- El chat `/agent/chat` invoca el CLI Hermes del sistema. Hermes no se instala
  en esta imagen, así que el chat no podrá redactar respuestas en el despliegue
  EC2 hasta que se configure Hermes y sus credenciales en el contenedor. La
  interfaz y los endpoints que no dependen de Hermes sí pueden arrancar.
- El endpoint `/health` comprueba la API, no la conexión con Firebase, Gmail
  ni Hermes.

## Preparar la instancia EC2

Usa una instancia Ubuntu 24.04 LTS con acceso SSH restringido a tu IP. En el
Security Group, deja el puerto 22 limitado a tu IP. Para la
prueba inicial, limita también el 80 a tu IP; configura HTTPS en un proxy o
balanceador antes de habilitar tráfico público.

Conéctate por SSH e instala Docker Engine y el plugin de Compose desde el
repositorio oficial de Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin git
sudo usermod -aG docker "$USER"
```

Cierra la sesión SSH y vuelve a conectarte para que se aplique el grupo `docker`.
Verifica la instalación:

```bash
docker --version
docker compose version
```

## Clonar, configurar secretos y arrancar

```bash
git clone https://github.com/Edinson99/SoporteTI-Agent.git
cd SoporteTI-Agent
cp .env.example .env
mkdir -p secrets .secrets
chmod 700 secrets .secrets
```

Edita `.env` y completa solo las variables de integraciones que vayas a usar.
Nunca copies `.env` ni archivos de credenciales al repositorio ni a la imagen.
El directorio `data/` se monta en el contenedor para persistir la base de
conocimiento y las bases SQLite. El usuario del contenedor tiene UID 1000; si
la instancia creó `data/` con otro propietario, dale acceso al UID/GID 1000:

```bash
sudo chown -R 1000:1000 data
```

Si habilitas Firebase Data Connect, configura en `.env`:

```dotenv
SOPORTE_TICKETS_BACKEND=firebase
FIREBASE_PROJECT_ID=soporteit-tickets
DATA_CONNECT_SERVICE_ID=soporteit-tickets-service
DATA_CONNECT_LOCATION=us-east4
```

Coloca la clave de la cuenta de servicio autorizada para Data Connect en
`secrets/serviceAccountKey.json`. El Compose la monta como solo lectura y
configura `GOOGLE_APPLICATION_CREDENTIALS`. No es necesaria cuando se conserva
el backend SQLite predeterminado. Protege la clave y limita los permisos de
acceso al servidor.

Para correo Gmail, coloca el cliente OAuth y el token en `.secrets/` usando los
nombres configurados en `.env.example`. El directorio se monta con escritura
porque la aplicación actualiza el token cuando renueva credenciales; protege
ese directorio en el host y no concedas acceso a otros usuarios.

Construye y arranca:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f soporteti-agent
```

En otra terminal, comprueba el health check y abre la interfaz:

```bash
curl -fsS http://localhost/health
```

La interfaz web y la API quedan en `http://IP_PUBLICA_EC2/` y
`http://IP_PUBLICA_EC2/docs`. No publiques el servicio abiertamente sin
autenticación y HTTPS; consulta las limitaciones de seguridad anteriores.

## Actualizar y operar

Desde el directorio del repositorio en EC2:

```bash
git pull
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 soporteti-agent
```

Haz copias de seguridad de `data/` antes de actualizar o reemplazar la instancia.
Los directorios `secrets/` y `.secrets/` contienen credenciales y deben
respaldarse por separado con controles de acceso adecuados.
