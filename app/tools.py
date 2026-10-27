"""Herramientas locales y seguras del agente de soporte TI."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

_BASE_CONOCIMIENTO = Path(__file__).resolve().parent.parent / "data" / "conocimiento_soporte.json"


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"[^\w]+", " ", sin_acentos).strip()


@lru_cache(maxsize=1)
def cargar_base_conocimiento() -> list[dict[str, Any]]:
    """Carga una vez los articulos de soporte versionados con la aplicacion."""
    with _BASE_CONOCIMIENTO.open(encoding="utf-8") as archivo:
        return json.load(archivo)["articulos"]


def buscar_conocimientos(problema: str) -> list[dict[str, Any]]:
    """Devuelve articulos ordenados por coincidencias completas normalizadas."""
    texto = f" {_normalizar(problema)} "
    resultados: list[dict[str, Any]] = []

    for articulo in cargar_base_conocimiento():
        palabras_coincidentes: list[str] = []
        for palabra in articulo["palabras_clave"]:
            palabra_normalizada = _normalizar(palabra)
            if palabra_normalizada and f" {palabra_normalizada} " in texto:
                palabras_coincidentes.append(palabra)

        if palabras_coincidentes:
            puntuacion = sum(
                1 + len(_normalizar(palabra).split()) + min(len(palabra) / 40, 1)
                for palabra in palabras_coincidentes
            )
            resultados.append(
                {
                    "articulo": articulo,
                    "puntuacion": puntuacion,
                    "palabras_coincidentes": palabras_coincidentes,
                }
            )

    return sorted(resultados, key=lambda resultado: resultado["puntuacion"], reverse=True)


def buscar_conocimiento(problema: str) -> dict[str, Any] | None:
    """Mantiene la interfaz existente y devuelve el articulo mejor clasificado."""
    resultados = buscar_conocimientos(problema)
    return resultados[0]["articulo"] if resultados else None

def crear_borrador_ticket(problema: str, usuario: str) -> dict[str, str]:
    """Prepara un borrador; no crea ni modifica tickets reales."""
    return {
        "estado": "borrador_pendiente_aprobacion",
        "titulo": f"Revision de soporte para {usuario}",
        "descripcion": problema,
    }