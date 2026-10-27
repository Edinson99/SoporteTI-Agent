"""Orquestador determinista del agente de soporte TI."""

from __future__ import annotations

from typing import Any

from app.diagnostics import (
    crear_diagnostico,
    obtener_prioridad,
    obtener_preguntas_seguimiento,
)
from app.tools import buscar_conocimientos, crear_borrador_ticket


class AgenteSoporteTI:
    """Orquesta busqueda local y diagnostico guiado sin ejecutar acciones."""

    def responder(self, question: str, user_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        resultados = buscar_conocimientos(question)
        articulo = resultados[0]["articulo"] if resultados else None
        diagnostico = crear_diagnostico(resultados, context)
        preguntas = obtener_preguntas_seguimiento(context)
        dispositivo = (context or {}).get("device", "el equipo")
        acciones = articulo["pasos"] if articulo else []

        if articulo is None:
            borrador = crear_borrador_ticket(question, user_id)
            return {
                "answer": (
                    f"No encontre una guia segura para {dispositivo}. Se preparo un borrador para "
                    "revision humana; no se enviara ni se ejecutara ningun cambio automaticamente."
                ),
                "sources": ["protocolo_escalamiento"],
                "needs_approval": True,
                "next_action": borrador["estado"],
                "incident_id": None,
                "category": diagnostico["category"],
                "priority": obtener_prioridad(diagnostico["category"]),
                "diagnosis": diagnostico["diagnosis"],
                "evidence": diagnostico["evidence"],
                "confidence": diagnostico["confidence"],
                "recommended_actions": [],
                "escalation_reason": "No se encontro una guia relacionada en la base local.",
                "follow_up_questions": preguntas,
            }

        pasos = " ".join(f"{indice}. {paso}" for indice, paso in enumerate(articulo["pasos"], start=1))
        return {
            "answer": f"Para {dispositivo}: {pasos}",
            "sources": [resultado["articulo"]["id"] for resultado in resultados[:3]],
            "needs_approval": False,
            "next_action": "recopilar_datos" if preguntas else "seguir_pasos_seguros",
            "incident_id": None,
            "category": diagnostico["category"],
            "priority": obtener_prioridad(diagnostico["category"]),
            "diagnosis": diagnostico["diagnosis"],
            "evidence": diagnostico["evidence"],
            "confidence": diagnostico["confidence"],
            "recommended_actions": acciones,
            "escalation_reason": None,
            "follow_up_questions": preguntas,
        }