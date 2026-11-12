# Notas de versión 1.4.0

La versión 1.4.0 completa las etapas 2–5 de la fase de mejora. Las
integraciones externas son opcionales y requieren configuración por entorno;
no se incluyen secretos ni se realizan envíos reales durante las pruebas
automatizadas.

## Cambios

- **Observabilidad minimizada:** agrega métricas en memoria para solicitudes,
  códigos HTTP, errores 5xx y latencia. `GET /api/metrics` requiere loopback.
  El límite predeterminado es 60 solicitudes por minuto por ruta, proceso y
  origen de conexión; se configura con `SOPORTE_RATE_LIMIT_PER_MINUTE`.
- **Sentry opcional:** se activa con `SENTRY_DSN` y la dependencia de
  `requirements-observability.txt`. Los eventos se filtran para excluir
  solicitudes, identidad, mensajes, variables locales y breadcrumbs.
- **Correo resiliente:** Gmail permanece como proveedor principal y Resend
  puede respaldarlo cuando Gmail no está configurado o falla. El ticket
  conserva el resultado y la clase de error del envío.
- **Avisos Slack:** los webhooks HTTPS de `hooks.slack.com` pueden recibir
  alertas solo para tickets `high`/`critical`, limitadas al número, categoría
  y prioridad. El estado de la alerta se persiste y audita.
- **Retención de capturas:** las imágenes privadas se eliminan al resolver el
  ticket o al superar 180 días. La limpieza se ejecuta al crear, listar o
  resolver tickets y al consultar adjuntos.
- **Telegram puntual:** se ofrece un cliente MTProto opcional para una cuenta
  personal, con `/start` y `/consulta <problema>` restringidos a una lista
  permitida de IDs. Usa las guías locales, limita la consulta a 500 caracteres,
  no invoca Hermes, no crea tickets y no conserva mensajes ni historial. El
  cliente requiere una sesión local protegida. El webhook de Bot API permanece
  disponible como alternativa separada.
- **Página de estado:** `/status` y `GET /api/status` muestran liveness y
  configuración resumida. No sondean proveedores externos ni certifican su
  disponibilidad real; la página indica cuándo sus datos están desactualizados.

## Configuración opcional

- Sentry: `SENTRY_DSN`; instalar `requirements-observability.txt`.
- Resend: `RESEND_API_KEY`, `RESEND_FROM` y `RESEND_TO_EMAIL`.
- Slack: `SLACK_WEBHOOK_URL`.
- Telegram MTProto: instalar `requirements-telegram-mtproto.txt` y configurar
  `TELEGRAM_MTPROTO_API_ID`, `TELEGRAM_MTPROTO_API_HASH` y
  `TELEGRAM_MTPROTO_ALLOWED_USER_IDS`. El inicio de sesión inicial es
  interactivo y la sesión queda en `.secrets/`.
- Telegram Bot API legacy: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` y
  `TELEGRAM_WEBHOOK_SECRET`; registrar el webhook con HTTPS y el secreto como
  `secret_token`.
- Límite por proceso: `SOPORTE_RATE_LIMIT_PER_MINUTE`.

Configura secretos únicamente en el entorno autorizado y no los agregues al
repositorio. El panel de tickets continúa restringido a loopback y no
implementa autenticación de técnicos. El rate limit y la deduplicación de
Telegram son locales a cada proceso. La página de estado muestra configuración,
no una prueba de conectividad de dependencias.

Consulta el [contrato de API](api-contract.md), la
[arquitectura](arquitectura.md) y el estado de cada etapa en la
[fase de mejora](fase-mejora.md).

La validación real de proveedores externos del 11 de noviembre de 2026 está
documentada en [validacion-integraciones-2026-11-11.md](validacion-integraciones-2026-11-11.md).
La [fase de mejora](fase-mejora.md) relaciona esos resultados con el plan
original, marca los pendientes y propone prioridades para iteraciones futuras.
