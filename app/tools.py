"""Herramientas locales y seguras del agente de soporte TI."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

_BASE_CONOCIMIENTO = Path(__file__).resolve().parent.parent / "data" / "conocimiento_soporte.json"
_MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_UMBRAL_SIMILITUD_SEMANTICA = 0.65


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


def _busqueda_semantica_habilitada() -> bool:
    valor = os.getenv("SOPORTE_SEMANTIC_SEARCH", "false").strip().casefold()
    if valor not in {"true", "false"}:
        raise ValueError("SOPORTE_SEMANTIC_SEARCH debe ser 'true' o 'false'.")
    return valor == "true"


@lru_cache(maxsize=1)
def _obtener_modelo_embeddings() -> Any:
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise RuntimeError(
            "La busqueda semantica requiere fastembed; instala "
            "requirements-semantic.txt."
        ) from error

    cache_base = Path(
        os.getenv("LOCALAPPDATA", str(Path.home() / ".cache"))
    )
    directorio_cache = cache_base / "SoporteTI-Agent" / "fastembed"
    directorio_cache.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(
        model_name=_MODELO_EMBEDDINGS,
        cache_dir=str(directorio_cache),
    )


@lru_cache(maxsize=1)
def _obtener_indice_semantico() -> tuple[tuple[float, ...], ...]:
    articulos = cargar_base_conocimiento()
    textos = [
        " ".join(
            [
                *articulo["palabras_clave"],
                *articulo["pasos"],
            ]
        )
        for articulo in articulos
    ]
    embeddings = tuple(
        tuple(float(valor) for valor in vector)
        for vector in _obtener_modelo_embeddings().embed(textos)
    )
    if len(embeddings) != len(textos):
        raise RuntimeError("El modelo no devolvio un embedding por cada articulo.")
    return embeddings


def _similitud_coseno(
    vector_a: tuple[float, ...],
    vector_b: tuple[float, ...],
) -> float:
    if len(vector_a) != len(vector_b):
        raise ValueError("Los embeddings deben tener la misma dimension.")
    norma_a = math.sqrt(sum(valor * valor for valor in vector_a))
    norma_b = math.sqrt(sum(valor * valor for valor in vector_b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return sum(a * b for a, b in zip(vector_a, vector_b)) / (norma_a * norma_b)


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

    if _busqueda_semantica_habilitada():
        articulos = cargar_base_conocimiento()
        embeddings = _obtener_indice_semantico()
        embeddings_consulta = tuple(
            float(valor)
            for vector in _obtener_modelo_embeddings().embed([problema])
            for valor in vector
        )
        dimension = len(embeddings[0]) if embeddings else 0
        if not embeddings_consulta or len(embeddings_consulta) != dimension:
            raise RuntimeError("El modelo no devolvio un embedding valido para la consulta.")
        resultados_por_id = {
            resultado["articulo"]["id"]: resultado for resultado in resultados
        }

        for articulo, embedding_articulo in zip(articulos, embeddings):
            similitud = _similitud_coseno(embeddings_consulta, embedding_articulo)
            resultado = resultados_por_id.get(articulo["id"])
            if resultado is not None:
                if similitud >= _UMBRAL_SIMILITUD_SEMANTICA:
                    resultado["similitud_semantica"] = round(similitud, 4)
                    resultado["metodo_busqueda"] = "hibrida"
            elif similitud >= _UMBRAL_SIMILITUD_SEMANTICA:
                resultados.append(
                    {
                        "articulo": articulo,
                        "puntuacion": 1,
                        "palabras_coincidentes": [],
                        "similitud_semantica": round(similitud, 4),
                        "metodo_busqueda": "semantica",
                    }
                )

    return sorted(
        resultados,
        key=lambda resultado: (
            "similitud_semantica" in resultado,
            resultado.get("similitud_semantica", 0.0),
            resultado["puntuacion"],
        ),
        reverse=True,
    )


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