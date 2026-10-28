# Contrato de la API v1.3.8

Este archivo conserva la ruta de documentación utilizada en versiones
anteriores. El contrato completo y vigente, incluidos esquemas, ejemplos,
validaciones y estados HTTP, está centralizado en
[api-contract.md](api-contract.md).

## Endpoints actuales

| Método y ruta | Función | Acceso |
| --- | --- | --- |
| `GET /health` | Comprueba que la API responde. | API local o despliegue configurado |
| `POST /agent/ask` | Diagnóstico determinista con la base de conocimiento local. | API |
| `POST /agent/chat` | Diagnóstico local y respuesta de Hermes; web oficial cuando hace falta y visión si hay capturas. | Solo loopback |
| `POST /agent/tickets` | Crea y notifica un ticket sin guía después de obtener datos de contacto y consentimiento. | Solo loopback |
| `GET /tickets` | Interfaz local de seguimiento y gestión. | Solo loopback |
| `GET /api/tickets` | Lista tickets y metadatos de adjuntos, sin incluir bytes de imagen. | Solo loopback |
| `GET /api/tickets/{ticket_number}/attachments/{attachment_id}` | Sirve una captura guardada en el ticket. | Solo loopback |
| `POST /api/tickets/{ticket_number}/resolve` | Guarda nota y marca el ticket como resuelto. | Solo loopback |

## Cambios de la versión 1.3.5

Las notificaciones de ticket usan Gmail API OAuth. La firma de la cuenta
remitente se consulta en Gmail y se agrega al correo. Consulta las
[notas de versión 1.3.5](version-1.3.5.md) para los requisitos, el archivo OAuth
local, la autorización y los permisos.

## Cambios posteriores

- **1.3.6:** el panel local incorpora búsqueda, filtros, conteos y acceso al
  diagnóstico y contexto del ticket. Consulta las
  [notas 1.3.6](version-1.3.6.md).
- **1.3.7:** el chat puede recopilar aclaraciones, consultar documentación web
  oficial y analizar capturas. Los adjuntos solo se conservan en el ticket tras
  el consentimiento; no se envían por correo. Consulta las
  [notas 1.3.7](version-1.3.7.md).
- **1.3.8:** el chat responde en español sin tildes ni `ñ`; el correo normaliza
  también el asunto, el contenido y la firma de Gmail. Consulta las
  [notas 1.3.8](version-1.3.8.md).

La lógica determinista compartida no ejecuta comandos ni modifica equipos.
El panel y las rutas de tickets no autentican técnicos; mantenlos en loopback
y en equipos de confianza.
