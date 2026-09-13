"""Utilidades compartidas: slugs, validación de fecha y detección de fuente."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime


def slug_programa(programa: str, fecha: str, fuente: str) -> str:
    """Identificador estable de un capítulo, para nombrar los archivos de caché.

    Combina programa + fecha + un hash corto de la fuente, de modo que
    reprocesar la misma entrada reutiliza los mismos archivos.
    """
    base = _slugify(f"{programa}-{fecha}")
    h = hashlib.sha1(fuente.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{h}"


def _slugify(texto: str) -> str:
    """Convierte un texto en un slug apto para nombre de archivo."""
    texto = quitar_tildes(texto).lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-")


def quitar_tildes(texto: str) -> str:
    """Elimina tildes/diacríticos conservando la letra base."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def validar_fecha(fecha: str) -> str:
    """Valida que la fecha sea YYYY-MM-DD. Devuelve la misma cadena o lanza error."""
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Fecha inválida: '{fecha}'. Usa el formato YYYY-MM-DD (ej. 2026-09-13)."
        )
    return fecha


def es_url(fuente: str) -> bool:
    """True si la fuente parece una URL (http/https), False si es ruta local."""
    return fuente.lower().startswith(("http://", "https://"))
