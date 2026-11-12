"""Pruebas de almacenamiento local minimizado de feedback."""

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(
    app,
    base_url="http://127.0.0.1",
    client=("127.0.0.1", 8001),
)


def test_feedback_guarda_solo_voto_anonimo_y_resume_por_guia(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "feedback.sqlite3"
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(database_path))

    response = client.post(
        "/api/feedback",
        json={
            "article_id": "kb_internet_001",
            "rating": "useful",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
    summary = client.get("/api/feedback/summary")
    assert summary.status_code == 200
    assert summary.json() == [
        {
            "article_id": "kb_internet_001",
            "useful": 1,
            "not_useful": 0,
            "total": 1,
        }
    ]

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(feedback_votes)")
        }
    assert columns == {"article_id", "rating", "created_at"}


def test_feedback_agrupa_valoraciones_por_guia(tmp_path, monkeypatch):
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))
    request = {
        "article_id": "kb_correo_001",
        "rating": "not_useful",
    }

    first = client.post("/api/feedback", json=request)
    second = client.post(
        "/api/feedback",
        json={**request, "rating": "useful"},
    )

    assert first.json() == {"status": "recorded"}
    assert second.json() == {"status": "recorded"}
    assert client.get("/api/feedback/summary").json() == [
        {
            "article_id": "kb_correo_001",
            "useful": 1,
            "not_useful": 1,
            "total": 2,
        }
    ]


def test_feedback_rechaza_valoracion_fuera_del_contrato(tmp_path, monkeypatch):
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))
    response = client.post(
        "/api/feedback",
        json={
            "article_id": "kb_correo_001",
            "rating": "maybe",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Solicitud invalida."


def test_feedback_rechaza_guia_desconocida(tmp_path, monkeypatch):
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))

    response = client.post(
        "/api/feedback",
        json={
            "article_id": "kb_no_existe",
            "rating": "useful",
        },
    )

    assert response.status_code == 400
    assert "guia valorada no existe" in response.json()["errors"][0]["msg"]


def test_feedback_y_resumen_rechazan_clientes_remotos():
    remote_client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("192.168.1.10", 8001),
    )

    assert remote_client.post(
        "/api/feedback",
        json={
            "article_id": "kb_internet_001",
            "rating": "useful",
        },
    ).status_code == 403
    assert remote_client.get("/api/feedback/summary").status_code == 403


def test_feedback_informa_fallos_de_persistencia(tmp_path, monkeypatch):
    database_path = tmp_path / "not-a-database"
    database_path.mkdir()
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(database_path))

    response = client.post(
        "/api/feedback",
        json={
            "article_id": "kb_internet_001",
            "rating": "useful",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "No fue posible guardar la valoracion local."


def test_resumen_sin_valoraciones_es_lista_vacia(tmp_path, monkeypatch):
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))

    assert client.get("/api/feedback/summary").json() == []


def test_resumen_elimina_votos_mas_antiguos_de_180_dias(tmp_path, monkeypatch):
    database_path = tmp_path / "feedback.sqlite3"
    monkeypatch.setenv("SOPORTE_FEEDBACK_DB", str(database_path))
    old_date = (
        datetime.now(timezone.utc) - timedelta(days=181)
    ).isoformat(timespec="seconds")
    current_date = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE feedback_votes (
                article_id TEXT NOT NULL,
                rating TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO feedback_votes (article_id, rating, created_at)
            VALUES (?, ?, ?)
            """,
            [
                ("kb_internet_001", "useful", old_date),
                ("kb_correo_001", "not_useful", current_date),
            ],
        )

    assert client.get("/api/feedback/summary").json() == [
        {
            "article_id": "kb_correo_001",
            "useful": 0,
            "not_useful": 1,
            "total": 1,
        }
    ]
