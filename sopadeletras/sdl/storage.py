"""Etapa 5 del pipeline: almacenamiento en SQLite.

Guarda la transcripción completa de cada capítulo (texto + segmentos con
timestamps). Dedupe por (programa, fecha): reprocesar el mismo capítulo
no crea filas duplicadas.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

# Esquema de la base de datos. Diseñado para exportarlo luego a otra IA
# que hará: aislar preguntas, responderlas, clasificarlas y generar la app.
ESQUEMA = """
CREATE TABLE IF NOT EXISTS transcripciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    programa   TEXT NOT NULL,
    fecha      TEXT NOT NULL,          -- YYYY-MM-DD
    texto      TEXT NOT NULL,          -- transcripción completa
    segmentos  TEXT NOT NULL,          -- JSON: [{ts_inicio, ts_fin, texto}, ...]
    fuente     TEXT,                   -- URL o ruta original
    idioma     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(programa, fecha)            -- clave de dedupe
);

CREATE INDEX IF NOT EXISTS idx_transcripciones_programa
    ON transcripciones(programa);
"""


def conectar(db_path: Path) -> sqlite3.Connection:
    """Abre (y crea si hace falta) la base de datos, aplicando el esquema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def guardar_transcripcion(con: sqlite3.Connection, *, programa: str, fecha: str,
                          fuente: str, transcripcion: dict[str, Any],
                          force: bool = False) -> bool:
    """Inserta la transcripción de un capítulo.

    Devuelve True si se insertó/actualizó, False si ya existía y no se forzó.
    Con force=True reemplaza la fila existente (útil al re-transcribir).
    """
    texto = transcripcion.get("texto", "")
    segmentos = json.dumps(transcripcion.get("segmentos", []), ensure_ascii=False)
    idioma = transcripcion.get("idioma")

    existe = con.execute(
        "SELECT id FROM transcripciones WHERE programa = ? AND fecha = ?",
        (programa, fecha),
    ).fetchone()

    if existe and not force:
        return False

    if existe:
        con.execute(
            "UPDATE transcripciones SET texto = ?, segmentos = ?, fuente = ?, "
            "idioma = ? WHERE id = ?",
            (texto, segmentos, fuente, idioma, existe["id"]),
        )
    else:
        con.execute(
            "INSERT INTO transcripciones (programa, fecha, texto, segmentos, "
            "fuente, idioma) VALUES (?, ?, ?, ?, ?, ?)",
            (programa, fecha, texto, segmentos, fuente, idioma),
        )
    con.commit()
    return True


def existe_capitulo(con: sqlite3.Connection, programa: str, fecha: str) -> bool:
    """True si ya hay una transcripción para ese (programa, fecha)."""
    return con.execute(
        "SELECT 1 FROM transcripciones WHERE programa = ? AND fecha = ?",
        (programa, fecha),
    ).fetchone() is not None


def listar(con: sqlite3.Connection, programa: str | None = None) -> list[sqlite3.Row]:
    """Lista las transcripciones almacenadas, opcionalmente filtrando por programa."""
    sql = ("SELECT id, programa, fecha, fuente, idioma, "
           "length(texto) AS n_chars, created_at FROM transcripciones")
    params: list[Any] = []
    if programa:
        sql += " WHERE programa = ?"
        params.append(programa)
    sql += " ORDER BY fecha DESC, programa"
    return con.execute(sql, params).fetchall()


def obtener_todo(con: sqlite3.Connection,
                 programa: str | None = None) -> Iterable[sqlite3.Row]:
    """Devuelve las filas completas (con texto y segmentos) para exportar."""
    sql = ("SELECT id, programa, fecha, texto, segmentos, fuente, idioma, "
           "created_at FROM transcripciones")
    params: list[Any] = []
    if programa:
        sql += " WHERE programa = ?"
        params.append(programa)
    sql += " ORDER BY fecha DESC, programa"
    return con.execute(sql, params).fetchall()
