# Version 1.3.6

Se mejora el panel local de tickets disponible en
`http://127.0.0.1:8000/tickets`.

- Muestra totales de tickets abiertos y resueltos.
- Permite buscar por identificador, categoría, usuario, contacto o descripción
  y filtrar por estado.
- Da acceso al diagnóstico y contexto registrados, además de la conversación,
  datos de contacto y estado del correo.
- Conserva la opción de guardar una nota y marcar como resuelto cada ticket
  abierto.

El panel y sus rutas de datos siguen limitados a conexiones locales. Para usarlo,
inicia la aplicación con `.\scripts\start.ps1` y abre la dirección indicada.
