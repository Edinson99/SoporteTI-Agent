# Validación de integraciones externas — 2026-11-11

Se ejecutaron comprobaciones reales después de recibir autorización. Las
pruebas de correo y Slack usaron mensajes técnicos mínimos, sin tickets,
conversaciones, contactos ni datos de usuarios. No se registraron credenciales,
destinatarios, canales, IDs de mensaje ni contenidos de eventos.

| Integración | Prueba | Resultado |
| --- | --- | --- |
| Gmail | Envío de correo sintético al destinatario configurado y renovación OAuth. | **Correcto.** Gmail aceptó el mensaje de prueba; el token OAuth se renovó. |
| Resend | Envío de correo sintético al destinatario técnico configurado. | **Correcto.** La API respondió HTTP 200. |
| Slack | Publicación de mensaje sintético al webhook configurado. | **Correcto.** Slack respondió HTTP 200. |
| Firebase Data Connect | Operación de solo lectura para contar tickets; no se imprimieron sus datos. | **Correcto.** Se encontraron 11 tickets; no se modificaron registros. |
| Telegram MTProto | Conexión con la sesión local existente y comprobación de autorización. | **Correcto.** La sesión estaba autorizada. No se enviaron mensajes. |
| Sentry | Excepción sintética filtrada por `scrub_sentry_event`; espera del transporte. | **No confirmado.** El SDK creó el evento, pero la cola seguía con 2 elementos tras esperar hasta 45 segundos y no se observó respuesta HTTP. No se puede afirmar que Sentry lo recibiera. |

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
- Investigar la falta de respuesta del transporte Sentry antes de usarlo como
  canal operativo de monitoreo. La presencia del DSN en configuración no
  demuestra entrega de eventos.
- Mantener las credenciales y la sesión en archivos locales protegidos; este
  informe no contiene secretos ni identificadores de cuentas.
