# Version 1.3.4

La version 1.3.4 integra Hermes con el modelo configurado en cada turno del
chat, solicita autorizacion antes de escalar un caso sin guia y copia al
usuario en el correo enviado al tecnico.

## Conversacion Hermes/Kimi

- Cada consulta enviada desde el chat web llama a Hermes y al proveedor/modelo
  seleccionado en la configuracion de Hermes, incluidas las consultas sin guia.
- Si Hermes/Kimi no puede responder, el endpoint devuelve un error explicito;
  no se presenta la respuesta determinista como si la hubiera generado el
  modelo.
- La ruta de consulta directa `/agent/ask` conserva su comportamiento
  determinista y no invoca el modelo.

## Consentimiento de escalacion y copia al usuario

- Cuando no hay guia suficiente, Hermes redacta una respuesta que plantea el
  contacto con el tecnico; la interfaz explica que informacion se compartira.
- El ticket no se guarda ni se notifica hasta que el usuario ingresa sus datos
  y marca la autorizacion explicita.
- La API exige `consent_to_email: true`; una solicitud sin autorizacion se
  rechaza antes de crear el ticket.
- El correo de escalacion se envia al tecnico y agrega el correo de contacto
  del usuario en copia (`Cc`).

  ## Persistencia de tickets con Firebase Data Connect

  - Se puede usar Firebase Data Connect como backend para tickets, mensajes de
    conversacion y eventos de auditoria; SQLite se mantiene como opcion
    predeterminada.
  - La instancia configurada es el servicio `soporteit-tickets-service` en
    `us-east4`. Las operaciones guardan los datos en las tablas existentes de
    Cloud SQL por medio del conector `support`.
  - No se modifico el esquema SQL ni se importaron tickets de SQLite. La
    creacion del ticket, la conversacion y sus eventos iniciales se guarda en
    una operacion transaccional.
  - La aplicacion local requiere Node.js, `npm ci` y Application Default
    Credentials (ADC); `firebase login` no sustituye
    `gcloud auth application-default login`.
  - La integracion devuelve un error explicito ante credenciales o permisos
    ausentes y no cambia silenciosamente a SQLite.

  ## Verificacion

  Las pruebas validan que Hermes se invoca tambien para un problema sin guia,
  que la escalacion requiere consentimiento y que el correo incluye al usuario
  en copia. La integracion Data Connect se compila y sus pruebas automatizadas
  cubren creacion, idempotencia, consulta y resolucion de tickets.
