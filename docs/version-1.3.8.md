# Version 1.3.8

## Respuestas del asistente

- Hermes recibe instrucciones explicitas para responder en espanol sin tildes
  ni la letra `ñ`.
- El servidor normaliza la respuesta final, incluidas las preguntas de
  seguimiento agregadas por la API, para mantener el formato aunque el modelo
  no respete la instruccion.
- Se conservan signos de puntuacion, codigos de error, nombres tecnicos y
  URLs; la normalizacion solo quita diacriticos.

## Correos de tickets

- El asunto, el cuerpo de texto, el HTML y la firma consultada en Gmail se
  normalizan para quitar tildes y convertir `ñ`/`Ñ` en `n`/`N`.
- La configuracion local de Gmail se vuelve a cargar al enviar, de modo que
  los cambios en el archivo `.env` se apliquen sin que el proceso conserve
  valores anteriores.
- Se mantiene el remitente configurado como alias de envio valido en Gmail y
  la firma se consulta desde la cuenta antes de enviar.

La API publica esta version como `1.3.8`. Las pruebas de chat y correo cubren
las respuestas sin diacriticos, la firma normalizada y la carga de configuracion.
