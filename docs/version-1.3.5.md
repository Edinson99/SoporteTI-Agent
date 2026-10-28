# Version 1.3.5

La versión 1.3.5 cambió las notificaciones de escalación al envío mediante
Gmail API OAuth. Cada correo consulta la firma HTML configurada para la cuenta
remitente en Gmail y la agrega al mensaje, en lugar de mantener una copia
manual de la firma en la aplicación. La alternativa de texto plano también se
conserva. Esta es una nota histórica de esa versión; el panel y el chat se
ampliaron posteriormente en las versiones 1.3.6 y 1.3.7.

## Configuracion de Gmail API

1. En Google Cloud Console, crea o selecciona un proyecto, habilita **Gmail
   API** y configura la pantalla de consentimiento OAuth. Si la app OAuth está
   en modo de prueba, agrega la cuenta autorizada a la lista de usuarios de
   prueba.
2. Crea un ID de cliente OAuth de tipo **Aplicacion de escritorio** y descarga
   el JSON de cliente. Guárdalo localmente como
   `.secrets/gmail-oauth-client.json`; esa carpeta y el token están excluidos
   de Git. Evita OneDrive u otras carpetas compartidas para guardar credenciales.
3. En `.env`, configura `GMAIL_SENDER` y `GMAIL_TO_EMAIL` con las direcciones
   de tu organización y revisa `GMAIL_OAUTH_CLIENT_SECRETS` y
   `GMAIL_OAUTH_TOKEN_FILE`. No hay destinatarios personales predeterminados.
   El remitente debe corresponder a una dirección habilitada para enviar desde
   la cuenta autorizada.
4. Con la aplicación instalada en Windows, ejecuta desde la raíz del proyecto:

   ```powershell
   .\.venv\Scripts\python.exe scripts\authorize_gmail.py
   ```

   Se abrirá el navegador para autorizar el envío y la lectura de la firma. El
   token de renovación se guarda en `.secrets/gmail-token.json`; no lo compartas
   ni lo subas al repositorio. La cuenta autorizada debe coincidir con
   `GMAIL_SENDER` o tener esa dirección configurada como alias de envío válido.
5. Inicia o reinicia la aplicación. La firma de la dirección remitente se
   consulta en Gmail para cada correo, de modo que los cambios en Gmail se
   reflejan sin copiar la firma a `.env`.

El OAuth solicita únicamente los permisos `gmail.send` y
`gmail.settings.basic`. Si Google bloquea la autorización (por ejemplo,
`403 access_denied`), confirma que la API está habilitada, que la cuenta está
en la lista de usuarios de prueba y que la aplicación OAuth puede usarse con
ella. El ticket permanece guardado aunque el correo no se pueda enviar; el
estado de notificación registra si fue enviado o falló. Las capturas del ticket
no se adjuntan al correo.

## Verificacion

Las pruebas simulan Gmail API y comprueban que la firma HTML y su texto se
incluyen en el mensaje dirigido al técnico, además de conservar el manejo de
errores y la persistencia del ticket.
