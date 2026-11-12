"""Mide la recuperacion lexica e hibrida con consultas sinteticas etiquetadas."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tools import (
    _MODELO_EMBEDDINGS,
    _UMBRAL_SIMILITUD_SEMANTICA,
    buscar_conocimientos,
)

_CASOS_EVALUACION = ROOT / "data" / "retrieval_evaluation.json"


def _ids(resultados: list[dict[str, Any]]) -> list[str]:
    return [resultado["articulo"]["id"] for resultado in resultados]


def _porcentaje(aciertos: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{aciertos}/{total} ({aciertos / total:.0%})"


def evaluar_recuperacion() -> int:
    """Imprime metricas de recuperacion; retorna los falsos positivos sin guia."""
    evaluacion = json.loads(_CASOS_EVALUACION.read_text(encoding="utf-8"))
    casos = evaluacion["cases"]
    grupos = {"lexical": [], "paraphrase": [], "no_match": []}

    valor_original = os.environ.get("SOPORTE_SEMANTIC_SEARCH")
    try:
        os.environ["SOPORTE_SEMANTIC_SEARCH"] = "false"
        for caso in casos:
            ids_lexicos = _ids(buscar_conocimientos(caso["query"]))
            os.environ["SOPORTE_SEMANTIC_SEARCH"] = "true"
            ids_hibridos = _ids(buscar_conocimientos(caso["query"]))
            os.environ["SOPORTE_SEMANTIC_SEARCH"] = "false"

            esperado = caso["expected_article_id"]
            grupos[caso["group"]].append(
                {
                    "query": caso["query"],
                    "expected": esperado,
                    "group": caso["group"],
                    "lexical": ids_lexicos,
                    "hybrid": ids_hibridos,
                }
            )
    finally:
        if valor_original is None:
            os.environ.pop("SOPORTE_SEMANTIC_SEARCH", None)
        else:
            os.environ["SOPORTE_SEMANTIC_SEARCH"] = valor_original

    positivos = grupos["lexical"] + grupos["paraphrase"]

    def aciertos_top1(casos: list[dict[str, Any]], metodo: str) -> int:
        return sum(
            bool(caso[metodo]) and caso[metodo][0] == caso["expected"]
            for caso in casos
        )

    def aciertos_top3(casos: list[dict[str, Any]], metodo: str) -> int:
        return sum(
            caso["expected"] in caso[metodo][:3]
            for caso in casos
        )

    lexicos_top1 = aciertos_top1(positivos, "lexical")
    hibridos_top1 = aciertos_top1(positivos, "hybrid")
    hibridos_top3 = aciertos_top3(positivos, "hybrid")
    rescates_semanticos = sum(
        caso["expected"] not in caso["lexical"]
        and caso["expected"] in caso["hybrid"]
        for caso in positivos
    )
    falsos_positivos = [
        caso for caso in grupos["no_match"] if caso["hybrid"]
    ]

    print(evaluacion["description"])
    print(f"Modelo: {_MODELO_EMBEDDINGS}")
    print(f"Umbral de similitud: {_UMBRAL_SIMILITUD_SEMANTICA:.2f}")
    print(f"Aciertos lexicos @1: {_porcentaje(lexicos_top1, len(positivos))}")
    print(f"Aciertos hibridos @1: {_porcentaje(hibridos_top1, len(positivos))}")
    print(f"Cobertura hibrida @3: {_porcentaje(hibridos_top3, len(positivos))}")
    print(f"Rescates semanticos correctos: {rescates_semanticos}")
    print("Resultados por grupo:")
    for grupo in ("lexical", "paraphrase"):
        print(
            f"  {grupo}: lexico @1 "
            f"{_porcentaje(aciertos_top1(grupos[grupo], 'lexical'), len(grupos[grupo]))}; "
            f"hibrido @1 "
            f"{_porcentaje(aciertos_top1(grupos[grupo], 'hybrid'), len(grupos[grupo]))}; "
            f"hibrido @3 "
            f"{_porcentaje(aciertos_top3(grupos[grupo], 'hybrid'), len(grupos[grupo]))}"
        )
    print(
        "Falsos positivos en consultas sin guia: "
        f"{len(falsos_positivos)}/{len(grupos['no_match'])}"
    )

    errores = [
        caso
        for caso in positivos
        if not caso["hybrid"] or caso["hybrid"][0] != caso["expected"]
    ]
    for caso in errores:
        observado = caso["hybrid"][0] if caso["hybrid"] else "ninguno"
        print(
            f"MISS [{caso['group']}]: esperado={caso['expected']}; "
            f"observado={observado}; consulta={caso['query']}"
        )
    for caso in falsos_positivos:
        print(
            f"FALSE_POSITIVE: observado={caso['hybrid'][0]}; "
            f"consulta={caso['query']}"
        )

    return len(falsos_positivos)


if __name__ == "__main__":
    raise SystemExit(1 if evaluar_recuperacion() else 0)
