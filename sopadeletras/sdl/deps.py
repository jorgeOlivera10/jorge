"""Comprobación de dependencias externas (ffmpeg).

No instala nada: solo verifica y da mensajes claros de qué hacer si falta.
"""

from __future__ import annotations

import shutil
import subprocess


class DependenciaFaltante(RuntimeError):
    """Se lanza cuando falta una herramienta externa necesaria."""


def comprobar_ffmpeg() -> str:
    """Verifica que ffmpeg esté disponible y responda. Devuelve su ruta.

    Lanza DependenciaFaltante con instrucciones si no está.
    """
    ruta = shutil.which("ffmpeg")
    if not ruta:
        raise DependenciaFaltante(
            "No se encontró 'ffmpeg' en el PATH.\n"
            "Instálalo según tu sistema:\n"
            "  - Debian/Ubuntu:  sudo apt install ffmpeg\n"
            "  - macOS (brew):   brew install ffmpeg\n"
            "  - Windows:        https://ffmpeg.org/download.html\n"
            "Luego vuelve a ejecutar el comando."
        )

    # Confirmamos que arranca (a veces el binario existe pero está roto).
    try:
        subprocess.run(
            [ruta, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as e:
        raise DependenciaFaltante(
            f"'ffmpeg' se encontró en {ruta} pero no se pudo ejecutar: {e}"
        )

    return ruta


def comprobar_yt_dlp() -> str:
    """Verifica que yt-dlp esté disponible. Devuelve su ruta.

    Hace falta solo cuando la fuente es la URL de una página web (no un
    .m3u8 ni un archivo local). Lanza DependenciaFaltante con instrucciones.
    """
    ruta = shutil.which("yt-dlp")
    if not ruta:
        raise DependenciaFaltante(
            "Has pasado la URL de una página web, y para resolverla hace falta "
            "'yt-dlp', que no está instalado.\n"
            "Instálalo con:  pip install -U yt-dlp\n"
            "(O bien pasa directamente una URL .m3u8 o un archivo local, que no "
            "necesitan yt-dlp.)"
        )
    return ruta


def comprobar_faster_whisper() -> None:
    """Verifica que faster-whisper esté instalado (import)."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        raise DependenciaFaltante(
            "El paquete 'faster-whisper' no está instalado.\n"
            "Instálalo con: pip install -r requirements.txt"
        )
