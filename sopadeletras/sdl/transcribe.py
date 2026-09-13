"""Etapa 3 del pipeline: transcripción con faster-whisper.

Transcribe el WAV y guarda un JSON con el texto completo y los segmentos
con timestamps, para poder reutilizarlo sin re-transcribir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deps import comprobar_faster_whisper


def transcribir(wav: Path, destino_json: Path, cfg_whisper: dict[str, Any],
                force: bool = False) -> dict[str, Any]:
    """Transcribe 'wav' y guarda el resultado en 'destino_json'.

    Devuelve un dict con las claves: idioma, texto, segmentos.
    Cada segmento es {ts_inicio, ts_fin, texto}. Reutiliza la caché si existe.
    """
    if destino_json.exists() and not force:
        print(f"  [transcribe] Reutilizando caché: {destino_json.name}")
        with open(destino_json, "r", encoding="utf-8") as f:
            return json.load(f)

    comprobar_faster_whisper()
    from faster_whisper import WhisperModel  # import perezoso (arranque lento)

    modelo = cfg_whisper.get("modelo", "medium")
    idioma = cfg_whisper.get("idioma", "es")
    device = cfg_whisper.get("device", "auto")
    compute_type = cfg_whisper.get("compute_type", "auto")
    beam_size = int(cfg_whisper.get("beam_size", 5))

    print(f"  [transcribe] Cargando modelo whisper '{modelo}' "
          f"(device={device}, compute_type={compute_type})...")
    print("  [transcribe] La primera vez se descarga el modelo (puede tardar).")
    model = WhisperModel(modelo, device=device, compute_type=compute_type)

    print(f"  [transcribe] Transcribiendo {wav.name} (idioma={idioma})...")
    segmentos_gen, info = model.transcribe(
        str(wav),
        language=idioma,
        beam_size=beam_size,
    )

    # 'segmentos_gen' es un generador perezoso: al iterarlo se hace el trabajo.
    segmentos: list[dict[str, Any]] = []
    partes_texto: list[str] = []
    for seg in segmentos_gen:
        texto = seg.text.strip()
        segmentos.append({
            "ts_inicio": round(seg.start, 2),
            "ts_fin": round(seg.end, 2),
            "texto": texto,
        })
        partes_texto.append(texto)
        # Feedback de avance (la transcripción es larga con el modelo medium).
        print(f"    [{_fmt_ts(seg.start)}] {texto}")

    resultado = {
        "idioma": info.language,
        "texto": " ".join(partes_texto).strip(),
        "segmentos": segmentos,
    }

    destino_json.parent.mkdir(parents=True, exist_ok=True)
    with open(destino_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"  [transcribe] Guardado: {destino_json.name} "
          f"({len(segmentos)} segmentos)")

    return resultado


def _fmt_ts(segundos: float) -> str:
    """Formatea segundos como mm:ss para el log de avance."""
    m, s = divmod(int(segundos), 60)
    return f"{m:02d}:{s:02d}"
