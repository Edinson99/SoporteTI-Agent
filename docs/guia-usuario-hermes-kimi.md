# Guia para usuarios: chat local, Hermes y Kimi

Esta guia explica como iniciar la conversacion de soporte una vez que el equipo
ya fue configurado. No necesitas conocer Python ni modificar el agente para
utilizarlo.

## Que hace cada componente

- **Hermes** es el asistente con el que conversas.
- **Kimi** es el modelo que ayuda a Hermes a entender y redactar las respuestas.
- **SoporteTI-Agent** aporta las guias de soporte aprobadas mediante una
  herramienta llamada `consultar_soporte_ti`.
- **MCP** es el mecanismo que permite a Hermes consultar esa herramienta.

El modelo no cambia tu equipo. El chat no ejecuta arreglos ni crea un ticket
hasta que confirmes la escalacion y autorices compartir tus datos de contacto.
Recomienda pasos seguros o indica que el caso necesita revision humana.

## Iniciar Hermes desde Windows

1. Abre **Ubuntu** desde el menu Inicio de Windows. La terminal debe mostrar un
   indicador parecido a `javier@LAPTOP:~$`.
2. Comprueba que la herramienta de soporte este conectada:

   ```bash
   hermes mcp test soporte_ti
   ```

   El resultado debe indicar que se conecto y encontro
   `consultar_soporte_ti`.

3. Inicia Hermes:

   ```bash
   hermes
   ```

4. Dentro de la conversacion, escribe `/model` para comprobar que Kimi esta
   seleccionado. Si cambiaste la configuracion MCP recientemente, escribe
   `/reload-mcp`.
5. Describe el problema y pide que consulte la herramienta de soporte. Por
   ejemplo:

   > No tengo internet en mi portatil. Mi usuario es USR-1042. Consulta la
   > herramienta de soporte TI antes de recomendar pasos.

6. Para cerrar Hermes, presiona `Ctrl+D`.

## Usar el chat web personalizado con Hermes + Kimi

1. En PowerShell, desde la raiz del proyecto, inicia la aplicacion:

   ```powershell
   .\scripts\start.ps1
   ```

2. Abre la direccion que indica el servidor (por ejemplo,
   `http://127.0.0.1:8000`). El encabezado del chat muestra el modelo
   configurado para esa instalacion.
3. Describe la incidencia y, si ayuda, abre **Datos para afinar el
   diagnóstico** para indicar el sistema operativo, el alcance, el mensaje o
   código de error y los cambios recientes. También puedes adjuntar hasta tres
   capturas JPG, PNG o WebP de máximo 2 MiB cada una.
4. El chat obtiene primero el diagnóstico local. Si necesita más información,
   responde las preguntas de seguimiento; en casos sin guía suficiente puede
   pedir hasta dos aclaraciones antes de ofrecer escalar. Si deseas atención
   humana, también puedes pedir contactar al técnico directamente.
5. Si la guía local no basta, Hermes puede buscar documentación oficial y
   mostrar enlaces. Si adjuntas capturas, puede intentar leer los códigos y
   mensajes de error que sean visibles.

Hermes debe estar instalado y configurado en WSL. La API key no se introduce en
la página: la pregunta, el contexto, el diagnóstico, el historial y las capturas
del turno se envían al proveedor configurado mediante Hermes. Kimi es el
proveedor recomendado en esta guía, pero el administrador puede configurar
otro. No incluyas contraseñas, códigos MFA, claves ni información confidencial
en el texto o las imágenes. Si Hermes o el proveedor configurado no están
disponibles, la página mostrará un error explícito.

El historial y las capturas viven en la sesión actual del navegador y se
pierden al recargar la página. Las imágenes se conservan con el ticket solo
después de autorizar la escalación; aparecen en el panel local y no se adjuntan
al correo.

## Que esperar de la respuesta

- Si existe una guía local, Hermes puede resumir los pasos recomendados e
  indicar la fuente utilizada. La respuesta estructurada sigue procediendo del
  diagnóstico local.
- Si el problema no tiene una guia reconocida, te dira que requiere revision
  humana.
- Si hay varios problemas, describelos claramente y pide ayuda con uno a la
  vez para evitar diagnosticos confusos.

No compartas contraseñas, códigos de verificación, claves API ni información
confidencial en la conversación o las capturas. Las credenciales del modelo se
configuran de forma privada en Hermes y no se deben copiar a mensajes ni a
archivos del repositorio.

## Si no funciona

- Si `hermes` no se reconoce, confirma que abriste Ubuntu/WSL y no PowerShell.
- Si la prueba MCP falla, comunica el mensaje de error al administrador del
  proyecto; no edites la configuracion si no sabes cual es la ruta correcta.
- Si Hermes responde sin consultar soporte, inicia una nueva conversacion y
  pide explicitamente que use la herramienta de soporte TI.
- Si Kimi no responde, puede tratarse de la cuenta, la cuota o la conexion a la
  API. Solicita ayuda al administrador; nunca le envies tu clave API.

## Nota para quien administra el equipo

La instalacion inicial, las rutas de WSL, la configuracion de Kimi y los pasos
para reparar o validar la conexion estan descritos en la
[guia tecnica Hermes + Kimi](guia-tecnica-hermes-kimi.md).
