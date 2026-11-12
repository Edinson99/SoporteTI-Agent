# Validación de integraciones externas — 2026-11-11

Se ejecutaron comprobaciones reales después de recibir autorización y se
repitieron el mismo día para verificar el estado actual. Las pruebas de correo
y Slack usaron mensajes técnicos mínimos, sin tickets, conversaciones,
contactos ni datos de usuarios. No se registraron credenciales, destinatarios,
canales, IDs de mensaje ni contenidos de eventos.

| Integración | Prueba | Resultado |
| --- | --- | --- |
| Gmail | Envío de correo sintético al destinatario configurado y renovación OAuth. | **Correcto.** Gmail aceptó el mensaje de prueba; el token OAuth se renovó. |
| Resend | Envío de correo sintético al destinatario técnico configurado. | **Correcto.** La API respondió HTTP 200. |
| Slack | Publicación de mensaje sintético al webhook configurado. | **Correcto.** Slack respondió HTTP 200. |
| Firebase Data Connect | Operaciones de solo lectura para contar tickets; no se imprimieron sus datos. | **Correcto.** Lecturas satisfactorias (11 y 12 elementos en las comprobaciones); no se modificaron registros. |
| Telegram MTProto | Conexión con la sesión local existente y comprobación de autorización. | **Correcto.** La sesión estaba autorizada. No se enviaron mensajes. |
| Sentry | Excepción sintética filtrada por `scrub_sentry_event` y captura del estado HTTP del transporte. | **Correcto en la repetición.** El endpoint de ingesta respondió HTTP 200 y no se observó excepción de transporte. La primera comprobación no había capturado una respuesta; la repetición instrumentada confirmó la aceptación HTTP. |
| Hermes / modelo | Consulta sintética breve mediante `POST /agent/chat`, sin adjuntos ni creación de ticket. | **Correcto en la repetición.** La API devolvió HTTP 200, `chat_model_status=used` y respuesta. Un intento anterior dio HTTP 503; el reintento posterior funcionó, así que conviene vigilar errores transitorios. |

Las pruebas automatizadas focalizadas de notificaciones, observabilidad y
MTProto finalizaron con **22 pruebas aprobadas**. Hubo dos advertencias de
dependencias; no fallaron pruebas.

## Alcance y seguimiento

- La prueba de Gmail demuestra que se aceptó un correo de prueba; no certifica
  la entrega final ni el flujo completo de creación de tickets.
- Resend y Slack aceptaron las solicitudes de prueba. No se probó el camino de
  respaldo Gmail → Resend mediante un ticket real.
- Firebase solo se leyó; no se probaron escrituras ni eliminación.
- Telegram solo se conectó. No se envió un mensaje de prueba a la cuenta ni se
  ejercitó una consulta desde Telegram.
- Sentry devolvió HTTP 200 en la comprobación instrumentada; seguir observando
  la entrega y los errores de red en el entorno de ejecución.
- Hermes respondió a la repetición tras un 503 inicial. No se probaron
  herramientas web, visión ni conversaciones con datos reales.
- Mantener las credenciales y la sesión en archivos locales protegidos; este
  informe no contiene secretos ni identificadores de cuentas.
