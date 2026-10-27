# Version 1.3.3

La version 1.3.3 mejora el flujo de escalamiento local: primero solicita los
datos de contacto, luego crea y notifica el ticket, y permite al tecnico
registrar su resolucion.

## Confirmacion de contacto y creacion del ticket

- Cuando el diagnostico no encuentra una guia, el chat solicita nombre,
  correo y telefono mediante un formulario obligatorio.
- No se crea el ticket ni se envia correo hasta que el usuario envia el
  formulario.
- El correo incluye datos de contacto, usuario indicado, categoria, prioridad,
  descripcion, diagnostico, contexto y conversacion disponible.
- Cada confirmacion recibe un identificador de solicitud; repetirla por un
  fallo de red devuelve el mismo ticket sin crear ni notificar duplicados.
- El diagnóstico de `/agent/ask` tambien indica que se requiere contacto, pero
  no guarda ticket ni envia correo por si solo.
- Las consultas sin guia no requieren Hermes/Kimi para presentar el formulario;
  las consultas que encuentran guia conservan la redaccion del modelo.

El identificador del usuario no se autentica. El nombre, correo y telefono
provienen de lo que declara el usuario. Informa en la interfaz que esa
informacion se compartira con el tecnico y no solicites contraseñas, codigos
MFA ni secretos.

## Seguimiento y resolucion

- El panel local se encuentra en `/tickets` y permite ver casos abiertos y
  resueltos, datos de contacto, descripcion y conversacion.
- El tecnico puede marcar un ticket como resuelto y registrar una nota
  opcional; se conserva fecha y estado.
- El panel, la lista de tickets y el endpoint de resolucion solo aceptan
  solicitudes loopback.
- Las nuevas columnas se migran al leer o escribir la base SQLite ya existente;
  no se eliminan tickets anteriores.

El acceso loopback no autentica al tecnico. Usa el panel solo en un equipo
local de confianza y no expongas la aplicacion en una red compartida.

## Ampliacion de la base de conocimiento

Se incorporaron guias para DNS y rutas, recuperacion de datos, aplicaciones
ERP/CRM y politicas de grupo; correo movil, firma digital y videollamadas;
Moodle/Canvas y proyectores; libros Excel con macros, exportaciones CSV,
sincronizacion de nomina y diagnostico de puertos Docker/VS Code y GPU/RAM.

Se adaptaron las recomendaciones para priorizar observacion, preservar datos
y escalar cambios privilegiados. Se omitieron articulos que duplicaban guias
existentes y se descartaron instrucciones para abrir puertos, modificar
particiones/BIOS/registro, finalizar procesos a la fuerza o compartir datos
sensibles.

## Verificacion

Las pruebas cubren la solicitud previa de contacto, validacion de campos,
creacion idempotente, persistencia de datos de contacto, correo SMTP simulado,
migracion de la base previa, listado y cierre con fecha/nota; tambien comprueban
la clasificacion de las nuevas guias y sus limites de seguridad.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v
```
