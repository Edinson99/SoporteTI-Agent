"""Servidor MCP para exponer el diagnostico de soporte TI a Hermes."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.agent import AgenteSoporteTI
from app.main import AgentAskRequest


mcp = FastMCP("soporte-ti-agent")
_agent = AgenteSoporteTI()


@mcp.tool()
def consultar_soporte_ti(
    question: str,
    user_id: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Consulta guias locales; solo recomienda, no ejecuta cambios ni crea tickets."""
    request = AgentAskRequest.model_validate(
        {"question": question, "user_id": user_id, "context": context}
    )
    return _agent.responder(request.question, request.user_id, request.context)


def main() -> None:
    """Inicia el servidor MCP por stdio para clientes locales como Hermes."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
