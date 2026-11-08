"""Etapa opcional: descarga con yt-dlp.

Cuando la fuente es la URL de una página web (ej. aragonplay.es/watch/...),
yt-dlp resuelve el stream y descarga el mejor audio a un archivo local, que
luego pasa por la etapa de audio normal (ffmpeg -> WAV).

Esto te evita tener que sacar la URL .m3u8 a mano con el F12.
"""

from __future__ import annotations

import glob
import subprocess
from pathlib import Path

from .deps import comprobar_yt_dlp


def descargar_pagina(url: str, destino_dir: Path, slug: str,
                     navegador: str | None = None,
                     force: bool = False) -> Path:
    """Descarga el audio de una página web con yt-dlp. Devuelve la ruta del archivo.

    'navegador' (chrome/firefox/edge/...) hace que yt-dlp use las cookies de tu
    navegador, útil si el vídeo requiere haber iniciado sesión. Cacheado: si ya
    hay un archivo descargado para este slug, lo reutiliza.
    """
    yt_dlp = comprobar_yt_dlp()
    destino_dir.mkdir(parents=True, exist_ok=True)

    # ¿Ya está descargado? (buscamos cualquier archivo que empiece por el slug)
    existentes = _buscar_descarga(destino_dir, slug)
    if existentes and not force:
        print(f"  [descarga] Reutilizando caché: {existentes.name}")
        return existentes

    # Plantilla de salida: <slug>.<extensión que elija yt-dlp>
    plantilla = str(destino_dir / f"{slug}.%(ext)s")
    cmd = [
        yt_dlp,
        "-f", "bestaudio/best",   # nos basta con el audio
        "--no-playlist",          # solo este vídeo, no una lista entera
        "-o", plantilla,
    ]
    if navegador:
        cmd += ["--cookies-from-browser", navegador]
    cmd.append(url)

    print(f"  [descarga] Descargando con yt-dlp: {url}")
    if navegador:
        print(f"  [descarga] Usando las cookies de tu navegador: {navegador}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"yt-dlp no pudo descargar la página (código {e.returncode}).\n"
            "Posibles causas: el vídeo requiere iniciar sesión (prueba a añadir "
            "--navegador chrome), la web no está soportada, o el contenido tiene "
            "DRM. Como alternativa, saca la URL .m3u8 a mano (F12 -> Red -> m3u8) "
            "y pásala con --fuente."
        ) from e

    descargado = _buscar_descarga(destino_dir, slug)
    if not descargado:
        raise RuntimeError(
            "yt-dlp terminó sin error pero no se encontró el archivo descargado."
        )
    print(f"  [descarga] Guardado: {descargado.name}")
    return descargado


def _buscar_descarga(destino_dir: Path, slug: str) -> Path | None:
    """Busca un archivo descargado cuyo nombre empiece por el slug."""
    coincidencias = sorted(glob.glob(str(destino_dir / f"{slug}.*")))
    return Path(coincidencias[0]) if coincidencias else None
