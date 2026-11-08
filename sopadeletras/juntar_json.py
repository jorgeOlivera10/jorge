"""Junta todos los JSON de transcripciones en un único CSV.

Útil cuando has transcrito varios capítulos (p.ej. desde Google Colab) y los
tienes como archivos .json sueltos en una carpeta. Este script los recorre y
genera un CSV con una fila por capítulo, listo para pasárselo a otra IA.

Uso:
    python juntar_json.py CARPETA_CON_JSON [--salida transcripciones.csv]

Ejemplo (tras descargar la carpeta 'sopa' de tu Google Drive):
    python juntar_json.py ./sopa --salida todo.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Junta JSON de transcripciones en un CSV.")
    p.add_argument("carpeta", help="Carpeta que contiene los archivos .json")
    p.add_argument("--salida", default="transcripciones.csv",
                   help="Ruta del CSV de salida (por defecto transcripciones.csv)")
    args = p.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        print(f"No es una carpeta válida: {carpeta}")
        return 1

    archivos = sorted(carpeta.glob("*.json"))
    if not archivos:
        print(f"No se encontraron archivos .json en {carpeta}")
        return 1

    filas = []
    for ruta in archivos:
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [aviso] No se pudo leer {ruta.name}: {e}")
            continue
        filas.append({
            "archivo": ruta.name,
            "programa": d.get("programa", ""),
            "fecha": d.get("fecha", ""),
            "idioma": d.get("idioma", ""),
            "n_segmentos": len(d.get("segmentos", [])),
            "texto": d.get("texto", ""),
        })

    with open(args.salida, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=[
            "archivo", "programa", "fecha", "idioma", "n_segmentos", "texto"])
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"Hecho: {len(filas)} capítulos -> {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
