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


# Extensiones que ffmpeg puede leer directamente (stream o archivo de medios).
_EXT_MEDIA = (
    ".m3u8", ".mpd", ".mp4", ".mkv", ".webm", ".ts",
    ".m4a", ".mp3", ".aac", ".wav", ".ogg", ".flac", ".mov",
)


def tipo_fuente(fuente: str) -> str:
    """Clasifica la fuente para saber cómo tratarla.

    Devuelve:
      - "archivo"  : ruta a un archivo local existente.
      - "media"    : URL que apunta directamente a un medio (.m3u8/.mp4/...),
                     que ffmpeg puede leer sin descargar aparte.
      - "pagina"   : URL de una página web (ej. aragonplay.es/watch/...),
                     que hay que resolver con yt-dlp.
    """
    if not es_url(fuente):
        return "archivo"

    # Nos quedamos con la parte de la ruta, sin los parámetros (?token=...).
    ruta = fuente.split("?", 1)[0].lower()
    if ruta.endswith(_EXT_MEDIA):
        return "media"
    return "pagina"
