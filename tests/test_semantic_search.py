"""Pruebas locales de recuperacion semantica sin descargar el modelo."""

import pytest

import app.tools as tools
from app.diagnostics import crear_diagnostico


class FakeEmbeddingModel:
    def embed(self, textos):
        return [
            (1.0, 0.0)
            if "conectividad inalambrica" in texto
            else (0.0, 1.0)
            if "problema sin relacion" in texto
            else (1.0, 0.0)
            if "internet" in texto or "correo" in texto
            else (0.0, 1.0)
            for texto in textos
        ]


@pytest.fixture(autouse=True)
def knowledge_base(monkeypatch):
    articulos = [
        {
            "id": "kb_internet_001",
            "palabras_clave": ["internet", "wifi"],
            "pasos": ["Verifica la conexion de red."],
        },
        {
            "id": "kb_correo_001",
            "palabras_clave": ["correo", "outlook"],
            "pasos": ["Revisa la aplicacion de correo."],
        },
    ]
    monkeypatch.setattr(tools, "cargar_base_conocimiento", lambda: articulos)
    monkeypatch.setattr(tools, "_obtener_modelo_embeddings", lambda: FakeEmbeddingModel())
    tools._obtener_indice_semantico.cache_clear()
    yield articulos
    tools._obtener_indice_semantico.cache_clear()


def test_busqueda_semantica_retorna_coincidencias_y_evidencia(monkeypatch):
    monkeypatch.setenv("SOPORTE_SEMANTIC_SEARCH", "true")
    resultados = tools.buscar_conocimientos("conectividad inalambrica")

    assert resultados[0]["articulo"]["id"] == "kb_internet_001"
    assert resultados[0]["palabras_coincidentes"] == []
    assert resultados[0]["metodo_busqueda"] == "semantica"
    assert resultados[0]["similitud_semantica"] == pytest.approx(1.0)


def test_busqueda_semantica_conserva_y_enriquece_coincidencias_lexicas(monkeypatch):
    monkeypatch.setenv("SOPORTE_SEMANTIC_SEARCH", "true")
    resultados = tools.buscar_conocimientos("internet")

    internet = next(
        resultado
        for resultado in resultados
        if resultado["articulo"]["id"] == "kb_internet_001"
    )
    assert internet["palabras_coincidentes"] == ["internet"]
    assert internet["metodo_busqueda"] == "hibrida"
    assert internet["similitud_semantica"] == pytest.approx(1.0)


def test_busqueda_semantica_descarta_similitud_bajo_el_umbral(monkeypatch):
    monkeypatch.setenv("SOPORTE_SEMANTIC_SEARCH", "true")
    resultados = tools.buscar_conocimientos("problema sin relacion")

    assert resultados == []


def test_busqueda_lexica_no_inicializa_embeddings_si_la_funcion_esta_desactivada(
    monkeypatch,
):
    monkeypatch.setenv("SOPORTE_SEMANTIC_SEARCH", "false")

    resultados = tools.buscar_conocimientos("internet")

    assert resultados[0]["articulo"]["id"] == "kb_internet_001"
    assert "similitud_semantica" not in resultados[0]


def test_configuracion_semantica_rechaza_valores_desconocidos(monkeypatch):
    monkeypatch.setenv("SOPORTE_SEMANTIC_SEARCH", "enabled")

    with pytest.raises(ValueError, match="debe ser 'true' o 'false'"):
        tools.buscar_conocimientos("internet")


def test_diagnostico_expone_la_evidencia_semantica():
    resultado = crear_diagnostico(
        [
            {
                "articulo": {"id": "kb_internet_001"},
                "puntuacion": 1,
                "palabras_coincidentes": [],
                "similitud_semantica": 0.81,
                "metodo_busqueda": "semantica",
            }
        ],
        None,
    )

    assert resultado["confidence"] == 0.81
    assert resultado["evidence"] == ["Similitud semantica local: 0.81"]
    assert "Similitud semantica local" in resultado["diagnosis"]["hypotheses"][0]["rationale"]


def test_diagnostico_expone_evidencia_lexica_y_semantica_hibrida():
    resultado = crear_diagnostico(
        [
            {
                "articulo": {"id": "kb_internet_001"},
                "puntuacion": 2,
                "palabras_coincidentes": ["wifi"],
                "similitud_semantica": 0.74,
                "metodo_busqueda": "hibrida",
            }
        ],
        None,
    )

    assert resultado["evidence"] == [
        "Palabra clave coincidente: wifi",
        "Similitud semantica local: 0.74",
    ]
