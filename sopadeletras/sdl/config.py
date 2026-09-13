"""Carga de configuración.

Fusiona, por orden de prioridad (de menor a mayor):
  1. valores por defecto sensatos,
  2. lo que haya en config.yaml (si existe),
  3. overrides pasados por flags de la CLI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # PyYAML no instalado
    yaml = None


# Valores por defecto de toda la herramienta.
DEFAULTS: dict[str, Any] = {
    "whisper": {
        "modelo": "medium",
        "idioma": "es",
        "device": "auto",
        "compute_type": "auto",
        "beam_size": 5,
    },
    "rutas": {
        "data": "data",
    },
}


class Config:
    """Config resuelta, con accesos cómodos a rutas derivadas."""

    def __init__(self, datos: dict[str, Any]):
        self._d = datos

    # --- acceso a secciones -------------------------------------------------
    @property
    def whisper(self) -> dict[str, Any]:
        return self._d["whisper"]

    @property
    def data_dir(self) -> Path:
        return Path(self._d["rutas"]["data"]).expanduser()

    # --- rutas de caché derivadas ------------------------------------------
    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sopadeletras.db"

    def crear_directorios(self) -> None:
        """Crea las carpetas de trabajo si no existen."""
        for d in (self.data_dir, self.audio_dir, self.transcripts_dir):
            d.mkdir(parents=True, exist_ok=True)


def _merge(base: dict, extra: dict) -> dict:
    """Fusión recursiva: 'extra' pisa 'base'."""
    resultado = dict(base)
    for clave, valor in extra.items():
        if (
            clave in resultado
            and isinstance(resultado[clave], dict)
            and isinstance(valor, dict)
        ):
            resultado[clave] = _merge(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def cargar_config(ruta: str | os.PathLike | None = None,
                  overrides: dict[str, Any] | None = None) -> Config:
    """Devuelve la configuración final.

    'ruta' es un config.yaml opcional. 'overrides' es un dict parcial
    (normalmente construido a partir de los flags de la CLI) que se aplica
    al final.
    """
    datos = dict(DEFAULTS)

    # 1) config.yaml
    ruta_yaml = Path(ruta) if ruta else Path("config.yaml")
    if ruta_yaml.exists():
        if yaml is None:
            raise RuntimeError(
                "Se encontró config.yaml pero PyYAML no está instalado. "
                "Instálalo con: pip install -r requirements.txt"
            )
        with open(ruta_yaml, "r", encoding="utf-8") as f:
            del_yaml = yaml.safe_load(f) or {}
        datos = _merge(datos, del_yaml)

    # 2) overrides de la CLI (solo claves no nulas)
    if overrides:
        limpio = {
            seccion: {k: v for k, v in valores.items() if v is not None}
            for seccion, valores in overrides.items()
        }
        # quita secciones que quedaron vacías
        limpio = {s: v for s, v in limpio.items() if v}
        datos = _merge(datos, limpio)

    return Config(datos)
