# Version 1.3.7

Se amplía el chat local con Hermes:

- Recopila hasta dos respuestas de seguimiento antes de ofrecer escalar un caso
  sin guía local, salvo que el usuario solicite contactar al técnico.
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
