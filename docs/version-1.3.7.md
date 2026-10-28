# Version 1.3.7

Se amplía el chat local con Hermes:

- Hace una pregunta concreta para mantener el chat activo. Después de tres
  respuestas del usuario (tras la consulta inicial), ofrece contactar al
  técnico si la incidencia sigue sin resolverse, incluso si encontró guía;
  una petición explícita adelanta el formulario.
- Si la respuesta del modelo no termina con una pregunta, el servidor añade
  una pregunta de seguimiento basada en las guías locales.
- Puede consultar documentación oficial cuando la base local no basta y
  mostrar enlaces HTTPS permitidos.
- Acepta hasta tres capturas JPG, PNG o WebP de hasta 2 MiB cada una para leer
  mensajes y códigos de error visibles.
- Conserva las capturas en el ticket únicamente después del consentimiento.
  Se muestran en el panel local y no se adjuntan al correo.
- El historial del chat sigue limitado a la sesión actual de la página y se
  pierde al recargar.

El chat usa las herramientas web y, cuando hay imágenes, visión de Hermes; no
habilita terminal ni ejecución de comandos. Las preguntas, el contexto, el
historial y las capturas del turno se envían al proveedor configurado en
Hermes. No incluyas información confidencial en ellos.

Los correos al técnico ahora incluyen un diseño HTML adaptable con resumen,
etiqueta de prioridad, datos de contacto, contexto, conversación y la firma
configurada en Gmail. La alternativa de texto plano se mantiene para clientes
de correo que no muestran HTML.
