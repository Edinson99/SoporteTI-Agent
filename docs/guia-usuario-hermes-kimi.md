# Guia para usuarios: empezar a usar Soporte TI con Hermes y Kimi

Esta guia explica como iniciar la conversacion de soporte una vez que el equipo
ya fue configurado. No necesitas conocer Python ni modificar el agente para
utilizarlo.

## Que hace cada componente

- **Hermes** es el asistente con el que conversas.
- **Kimi** es el modelo que ayuda a Hermes a entender y redactar las respuestas.
- **SoporteTI-Agent** aporta las guias de soporte aprobadas mediante una
  herramienta llamada `consultar_soporte_ti`.
- **MCP** es el mecanismo que permite a Hermes consultar esa herramienta.

Kimi no cambia tu equipo. El agente tampoco ejecuta arreglos ni crea tickets
reales: recomienda pasos seguros o indica que el caso necesita revision humana.

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

## Que esperar de la respuesta

- Si existe una guia, Hermes puede resumir los pasos recomendados e indicar la
  fuente utilizada.
- Si el problema no tiene una guia reconocida, te dira que requiere revision
  humana.
- Si hay varios problemas, describelos claramente y pide ayuda con uno a la
  vez para evitar diagnosticos confusos.

No compartas contrasenas, codigos de verificacion, claves API ni informacion
confidencial en la conversacion. La clave de Kimi se configura de forma privada
en Hermes y no se debe copiar a mensajes ni a archivos del repositorio.

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
