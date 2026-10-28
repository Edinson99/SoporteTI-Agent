# Version 1.3.2

La version 1.3.2 incorpora persistencia local de tickets para incidencias sin
guia y su notificacion por correo. El flujo requiere primero los datos de
contacto del usuario y ofrece un panel local para que el tecnico siga y cierre
los casos. Estas funciones aplican al uso HTTP local; no despliegan ni modifican
EC2, Lambda ni MCP.

## Confirmacion y creacion de tickets

- Si el diagnostico no encuentra una guia, el chat solicita nombre, correo y
  telefono mediante un formulario obligatorio.
- No se crea el ticket ni se envia correo hasta que el usuario completa y
  confirma el formulario.
- Tras confirmar, se crea un identificador `STI-AAAAMMDD-######` y SQLite
  conserva el usuario indicado, datos de contacto, descripcion, categoria,
  prioridad, contexto, diagnostico y conversacion disponible.
- El ticket se guarda antes de intentar enviar el correo; un fallo de SMTP no
  elimina la incidencia.
- Cada solicitud de confirmacion usa un `request_id` idempotente para impedir
  tickets y notificaciones duplicadas al reintentar.
- `POST /agent/ask` y `POST /agent/chat` indican que se requiere contacto, pero
  no crean el ticket. El chat llama a `POST /agent/tickets` despues de obtener
  los datos. Esta ruta revalida que no exista una guia y solo admite clientes
  loopback.
- Las consultas sin guia no requieren Hermes/Kimi para presentar el formulario;
  las consultas que encuentran guia conservan la redaccion del modelo.
- Los estados del correo son `pending`, `sent`, `failed` y `not_configured`.
  Un fallo de correo no elimina el ticket persistido.

La base se crea por defecto en `data/tickets.sqlite3`, excluida del repositorio.
Puede cambiarse con `SOPORTE_TICKETS_DB`. El `user_id` y los datos de contacto
son valores declarados por el usuario, no una identidad autenticada.

## Seguimiento y resolucion

- El panel local del tecnico se sirve en `/tickets`.
- `GET /api/tickets` lista los casos con contacto, conversacion y estado.
- `POST /api/tickets/{ticket_number}/resolve` guarda el estado resuelto, la
  fecha y una nota opcional.
- Las columnas nuevas se agregan mediante migracion sin eliminar los tickets
  existentes.
- El panel y las rutas de lista y resolucion solo aceptan solicitudes loopback.

El acceso loopback no autentica al tecnico. Usa el panel solo en un equipo
local de confianza y no expongas el servidor en una red compartida.

## Configuracion local del correo

Define `GMAIL_SENDER` y `GMAIL_TO_EMAIL` en `.env` con direcciones de ejemplo
o con las direcciones autorizadas de tu organización. Para activar el envío:

La configuracion SMTP descrita originalmente en esta version fue reemplazada
en la version 1.3.5 por Gmail API OAuth, que añade la firma configurada en Gmail.
Consulta [las notas 1.3.5](version-1.3.5.md) para configurar la API y autorizar
la cuenta. Si falta el token OAuth, el ticket igualmente se conserva y la
interfaz indica que el correo no esta configurado. Ante un error de envio, el
ticket queda guardado y se informa el fallo.

## Privacidad y limites

El correo contiene el texto de la consulta, el usuario indicado, los datos de
contacto, categoria, prioridad, contexto y conversacion disponible. Las
capturas que se agregan en la version 1.3.7 se conservan en el ticket tras la
autorizacion y no se adjuntan al correo. No incluyas
contraseñas, codigos MFA, claves API ni datos confidenciales en el chat. La base
local contiene el mismo contenido del ticket; protegela con los permisos de tu
equipo. Esta version no añade autenticacion de usuarios o tecnicos ni
integracion externa con una mesa de servicio.

## Verificacion

La suite prueba la solicitud previa de contacto, validacion, creacion
idempotente, persistencia, correo Gmail API simulado, fallos y configuracion ausente,
migracion de la base previa, listado y cierre con fecha y nota.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

Consulta el [contrato HTTP](api-contract.md) para el detalle de las rutas y
respuestas.
