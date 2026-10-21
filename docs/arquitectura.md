# Arquitectura y Mapa de Componentes

## Decisiones v0.1

| Capa | Componente | Responsabilidad | Tecnologia |
| --- | --- | --- | --- |
| Interfaz | API HTTP | Recibe JSON y devuelve estados HTTP verificables. | FastAPI |
| Validacion | Modelos de solicitud/respuesta | Rechaza contratos invalidos sin procesarlos. | Pydantic |
| Orquestacion | `AgenteSoporteTI` | Analiza el objetivo, decide entre guia o escalacion y aplica limites. | Python |
| Herramientas | Busqueda y borrador de ticket | Consulta conocimiento y prepara, sin enviar, una escalacion. | Python |
| Integracion de agente | Servidor MCP stdio | Expone el diagnostico existente como herramienta para Hermes. | MCP Python SDK |
| Modelo | Proveedor configurado en Hermes | Genera la conversacion; Kimi se configura fuera de la aplicacion. | Kimi API |
| Datos | Base de conocimiento | Contiene diagnosticos y pasos seguros versionados. | JSON local |
| Configuracion | `.env.example` y `.gitignore` | Documenta variables y evita publicar secretos. | Variables de entorno |
| Calidad | Pruebas | Verifican JSON, diagnostico, escalacion y HTTP. | Pytest |

## Mapa del flujo

```mermaid
flowchart LR
    U[Usuario] -->|POST /agent/ask JSON| API[FastAPI]
    API --> V{Pydantic valida}
    V -->|Invalido| E[400 JSON legible]
    V -->|Valido| A[AgenteSoporteTI]
    A --> D{Decision}
    D -->|Problema conocido| K[buscar_conocimiento]
    K --> KB[data/conocimiento_soporte.json]
    KB --> R[Respuesta 200: pasos seguros + fuente]
    D -->|Sin guia| T[crear_borrador_ticket]
    T --> H[Respuesta 200: requiere aprobacion]
    Hermes[Hermes Agent] -->|MCP stdio| MCP[consultar_soporte_ti]
    Kimi[Kimi API] --> Hermes
    MCP --> A
    R --> U
    H --> U
```

Para la configuracion detallada de Hermes y Kimi, consulta
[la guia de integracion](hermes-kimi.md).

## Ciclo cloud-native del agente

1. **Objetivo:** resolver una incidencia descrita en `question`.
2. **Contexto:** recibe `user_id` y datos opcionales del dispositivo.
3. **Decision:** determina si existe un articulo de soporte aplicable.
4. **Herramientas:** consulta `conocimiento_soporte.json` o prepara un borrador de escalacion.
5. **Observacion:** devuelve `sources`, `next_action` y `needs_approval` para hacer visible el resultado.
6. **Limites:** no ejecuta comandos administrativos, no instala software, no cambia contrasenas, no modifica configuraciones criticas y no envia tickets automaticamente.

## Limite de la v0.1

La base de conocimiento y los borradores son locales y no persistentes. Un despliegue posterior debe añadir autenticacion, almacenamiento de tickets, observabilidad y un gestor de secretos.