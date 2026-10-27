# Version 1.3.0

La version 1.3.0 convierte la consulta de articulos en un flujo de diagnostico
guiado. El backend sigue siendo determinista y local: no es un sistema
autonomo de N1/N2 ni reemplaza la validacion de un tecnico.

## Mejoras incluidas

### Busqueda de conocimiento

- Normaliza mayusculas, acentos y puntuacion antes de comparar palabras
  completas.
- Carga la base JSON una vez por proceso, en vez de leerla en cada solicitud.
- Clasifica las coincidencias por puntuacion heuristica y puede devolver hasta
  tres fuentes relacionadas.
- Conserva `buscar_conocimiento` como interfaz compatible para los usos que
  necesitan un solo articulo.

La puntuacion mejora la ordenacion, pero no es busqueda semantica, no comprende
intencion y no incorpora RAG ni documentacion externa.

### Diagnostico conversacional

El agente ahora:

- Propone hipotesis provisionales basadas en las guias encontradas.
- Sugiere pruebas para ayudar a distinguir causas posibles.
- Pregunta por sistema operativo, alcance del incidente, mensaje de error y
  cambios recientes cuando esos datos no estan en el contexto.
- Interpreta `context.network_checks` para diferenciar una puerta de enlace
  inaccesible, un posible fallo DNS y un problema de salida a Internet.
- Separa expresamente los datos que el usuario declara de las observaciones que
  el servidor podria verificar.

Los valores de `network_checks` son declaraciones del solicitante. El agente no
ejecuta `ping`, consultas DNS ni otros comandos, y no verifica los resultados.
La confianza es una puntuacion heuristica de coincidencia, no una probabilidad
calibrada ni una confirmacion de causa raiz.

### Contrato y presentacion

La API v1.3.0 agrega estos campos de respuesta:

| Campo | Descripcion |
| --- | --- |
| `incident_id` | Actualmente `null`; aun no hay un sistema de tickets persistente. |
| `category` | Categoria heuristica de la incidencia. |
| `priority` | Prioridad inicial; los casos identificados como seguridad reciben `high`. |
| `diagnosis` | Resumen, hipotesis ordenadas y pruebas sugeridas. |
| `evidence` | Palabras clave coincidentes o resultados declarados por el usuario. |
| `confidence` | Relevancia heuristica de la hipotesis principal. |
| `recommended_actions` | Pasos de la guia local seleccionada. |
| `escalation_reason` | Motivo por el que se requiere revision humana, si aplica. |
| `follow_up_questions` | Preguntas correspondientes al contexto faltante. |

`answer`, `sources`, `needs_approval` y `next_action` se conservan. Los
adaptadores HTTP, Lambda y MCP comparten el mismo agente y entregan el contrato
ampliado. La interfaz web muestra hipotesis, pruebas, evidencia, preguntas y
prioridad.

## Persistencia y limites operativos

La version 1.3.0 no crea tickets persistentes: los borradores de escalacion
siguen siendo temporales y `incident_id` es `null`. Tampoco incluye
autenticacion para `user_id`, RAG, integraciones de mesa de servicio ni
comprobaciones ejecutadas en equipos. No se ejecutan comandos ni se aplican
cambios de configuracion; las acciones de modificacion siguen requiriendo
autorizacion y supervision humana.

No enviar contrasenas, codigos MFA, claves, tokens ni datos confidenciales en
la consulta. No exponer la API en redes publicas sin autenticacion y controles
de acceso.

## Verificacion

Las pruebas automatizadas cubren normalizacion de acentos, multiples
coincidencias, carga cacheada, preguntas de seguimiento, interpretacion
provisional de resultados DNS/puerta de enlace/Internet, prioridad de phishing
y contrato compartido HTTP, Lambda y MCP.

Ejecutar desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

Consulta tambien el [contrato HTTP](api-contract.md), el
[contrato de la aplicacion](contrato-api.md) y el
[mapa de arquitectura](arquitectura.md).
