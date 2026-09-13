"""Etapa 2 del pipeline: extracción de audio con ffmpeg.

Convierte una URL (.m3u8 / .mp4) o un archivo local a WAV mono 16 kHz,
que es el formato que espera faster-whisper. Idempotente y cacheado:
si el WAV ya existe, no vuelve a generarlo (salvo force=True).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .deps import comprobar_ffmpeg
from .utils import es_url


def extraer_audio(fuente: str, destino: Path, force: bool = False) -> Path:
    """Genera 'destino' (WAV mono 16 kHz) a partir de 'fuente'.

    'fuente' puede ser una URL de stream (.m3u8), un .mp4 o un archivo local.
    Devuelve la ruta del WAV. Reutiliza la caché si ya existe.
    """
    ffmpeg = comprobar_ffmpeg()

    if destino.exists() and not force:
        print(f"  [audio] Reutilizando caché: {destino.name}")
        return destino

    # Si es archivo local, comprobamos que exista antes de llamar a ffmpeg.
    if not es_url(fuente) and not Path(fuente).exists():
        raise FileNotFoundError(f"No existe el archivo de entrada: {fuente}")

    destino.parent.mkdir(parents=True, exist_ok=True)

    # Construimos el comando. Para streams añadimos flags de reconexión
    # que ayudan si el .m3u8 se corta a mitad.
    cmd: list[str] = [ffmpeg, "-y"]
    if es_url(fuente):
        cmd += [
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ]
    cmd += [
        "-i", fuente,
        "-vn",              # sin vídeo
        "-ac", "1",         # mono
        "-ar", "16000",     # 16 kHz
        "-f", "wav",
        str(destino),
    ]

    print(f"  [audio] Extrayendo audio de: {fuente}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        # Limpiamos un WAV parcial para no dejar caché corrupta.
        if destino.exists():
            destino.unlink()
        raise RuntimeError(
            f"ffmpeg falló al procesar la entrada (código {e.returncode}).\n"
            "Si es una URL .m3u8, comprueba que no haya caducado "
            "(vuelve a copiarla desde el navegador)."
        ) from e

    return destino
