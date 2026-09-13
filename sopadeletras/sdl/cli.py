"""Interfaz de línea de comandos (argparse).

Comandos:
  ingest        procesa una entrada (url/archivo + programa + fecha)
  ingest-batch  procesa muchas entradas desde un CSV (fuente,programa,fecha)
  list          lista las transcripciones almacenadas
  export        exporta a CSV y/o JSON para pasárselo a otra IA
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import audio, storage, transcribe
from .config import cargar_config, Config
from .deps import DependenciaFaltante
from .utils import es_url, slug_programa, validar_fecha


# ---------------------------------------------------------------------------
# Pipeline de una entrada
# ---------------------------------------------------------------------------
def _procesar_entrada(cfg: Config, fuente: str, programa: str, fecha: str,
                      force: bool = False, dry_run: bool = False) -> bool:
    """Ejecuta el pipeline completo para un capítulo. Devuelve True si se guardó."""
    fecha = validar_fecha(fecha)
    cfg.crear_directorios()

    slug = slug_programa(programa, fecha, fuente)
    print(f"\n=== {programa} · {fecha} ===")
    print(f"    fuente: {fuente}")

    # Si ya está en la BD y no forzamos, evitamos rehacer todo el trabajo.
    con = storage.conectar(cfg.db_path)
    if storage.existe_capitulo(con, programa, fecha) and not force and not dry_run:
        print("  [store] Este capítulo ya está en la base de datos. "
              "Usa --force para reprocesarlo.")
        con.close()
        return False

    # Etapa 2: audio
    wav = cfg.audio_dir / f"{slug}.wav"
    audio.extraer_audio(fuente, wav, force=force)

    # Etapa 3: transcripción
    json_transcripcion = cfg.transcripts_dir / f"{slug}.json"
    resultado = transcribe.transcribir(wav, json_transcripcion, cfg.whisper,
                                        force=force)

    if dry_run:
        print("  [dry-run] No se escribe en la BD. "
              f"Transcripción: {len(resultado.get('segmentos', []))} segmentos, "
              f"{len(resultado.get('texto', ''))} caracteres.")
        con.close()
        return False

    # Etapa 5: almacenamiento
    guardado = storage.guardar_transcripcion(
        con, programa=programa, fecha=fecha, fuente=fuente,
        transcripcion=resultado, force=force,
    )
    con.close()

    if guardado:
        print("  [store] Transcripción guardada en la base de datos.")
    else:
        print("  [store] Ya existía; no se ha modificado (usa --force).")
    return guardado


# ---------------------------------------------------------------------------
# Handlers de cada comando
# ---------------------------------------------------------------------------
def _cmd_ingest(args: argparse.Namespace, cfg: Config) -> int:
    _procesar_entrada(cfg, args.fuente, args.programa, args.fecha,
                      force=args.force, dry_run=args.dry_run)
    return 0


def _cmd_ingest_batch(args: argparse.Namespace, cfg: Config) -> int:
    ruta = Path(args.csv)
    if not ruta.exists():
        print(f"No existe el CSV: {ruta}", file=sys.stderr)
        return 1

    with open(ruta, "r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = set(lector.fieldnames or [])
        requeridas = {"fuente", "programa", "fecha"}
        if not requeridas.issubset(columnas):
            print(f"El CSV debe tener las columnas: {', '.join(sorted(requeridas))}",
                  file=sys.stderr)
            return 1
        filas = list(lector)

    total = len(filas)
    ok = 0
    for i, fila in enumerate(filas, 1):
        print(f"\n----- Entrada {i}/{total} -----")
        try:
            if _procesar_entrada(cfg, fila["fuente"].strip(),
                                 fila["programa"].strip(), fila["fecha"].strip(),
                                 force=args.force, dry_run=args.dry_run):
                ok += 1
        except Exception as e:  # no queremos que un capítulo tumbe toda la cola
            print(f"  [ERROR] {e}", file=sys.stderr)
    print(f"\nCola terminada: {ok}/{total} capítulos nuevos guardados.")
    return 0


def _cmd_list(args: argparse.Namespace, cfg: Config) -> int:
    con = storage.conectar(cfg.db_path)
    filas = storage.listar(con, programa=args.programa)
    con.close()
    if not filas:
        print("No hay transcripciones almacenadas todavía.")
        return 0
    print(f"{'ID':>3}  {'FECHA':<10}  {'PROGRAMA':<24}  {'CHARS':>7}  FUENTE")
    for r in filas:
        fuente = (r["fuente"] or "")[:50]
        print(f"{r['id']:>3}  {r['fecha']:<10}  {r['programa'][:24]:<24}  "
              f"{r['n_chars']:>7}  {fuente}")
    print(f"\nTotal: {len(filas)} capítulo(s).")
    return 0


def _cmd_export(args: argparse.Namespace, cfg: Config) -> int:
    con = storage.conectar(cfg.db_path)
    filas = list(storage.obtener_todo(con, programa=args.programa))
    con.close()

    if not filas:
        print("No hay nada que exportar.")
        return 0

    # Si no se especifica ni --csv ni --json, exportamos ambos por defecto.
    hacer_csv = args.csv or not (args.csv or args.json)
    hacer_json = args.json or not (args.csv or args.json)

    if hacer_json:
        destino = Path(args.json) if args.json else Path("transcripciones.json")
        datos = []
        for r in filas:
            datos.append({
                "id": r["id"],
                "programa": r["programa"],
                "fecha": r["fecha"],
                "fuente": r["fuente"],
                "idioma": r["idioma"],
                "texto": r["texto"],
                "segmentos": json.loads(r["segmentos"]),
                "created_at": r["created_at"],
            })
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        print(f"Exportado JSON: {destino} ({len(datos)} capítulos)")

    if hacer_csv:
        destino = Path(args.csv) if args.csv else Path("transcripciones.csv")
        with open(destino, "w", encoding="utf-8", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow(["id", "programa", "fecha", "fuente", "idioma",
                               "texto", "created_at"])
            for r in filas:
                escritor.writerow([r["id"], r["programa"], r["fecha"],
                                   r["fuente"], r["idioma"], r["texto"],
                                   r["created_at"]])
        print(f"Exportado CSV: {destino} ({len(filas)} capítulos)")

    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdl",
        description="Extrae y guarda transcripciones de 'Sopa de Letras' "
                    "(Aragón TV) para pasárselas luego a otra IA.",
    )
    p.add_argument("--config", help="Ruta a un config.yaml alternativo.")
    # Overrides globales de whisper (opcionales).
    p.add_argument("--whisper-modelo", dest="whisper_modelo",
                   help="Modelo de whisper (tiny/base/small/medium/large-v3).")
    p.add_argument("--idioma", help="Idioma del audio (por defecto es).")
    p.add_argument("--device", help="Dispositivo de whisper (auto/cpu/cuda).")
    p.add_argument("--data", help="Carpeta base de datos y caché.")

    sub = p.add_subparsers(dest="comando", required=True)

    # ingest
    pi = sub.add_parser("ingest", help="Procesa una entrada por el pipeline.")
    pi.add_argument("--fuente", required=True,
                    help="URL (.m3u8/.mp4) o ruta a un archivo local.")
    pi.add_argument("--programa", required=True, help="Nombre del programa.")
    pi.add_argument("--fecha", required=True, help="Fecha YYYY-MM-DD.")
    pi.add_argument("--force", action="store_true",
                    help="Rehace todas las etapas aunque haya caché.")
    pi.add_argument("--dry-run", action="store_true",
                    help="Transcribe pero no escribe en la BD.")
    pi.set_defaults(func=_cmd_ingest)

    # ingest-batch
    pb = sub.add_parser("ingest-batch",
                        help="Procesa una cola de entradas desde un CSV.")
    pb.add_argument("csv", help="CSV con columnas: fuente,programa,fecha")
    pb.add_argument("--force", action="store_true",
                    help="Rehace todas las etapas aunque haya caché.")
    pb.add_argument("--dry-run", action="store_true",
                    help="Transcribe pero no escribe en la BD.")
    pb.set_defaults(func=_cmd_ingest_batch)

    # list
    pl = sub.add_parser("list", help="Lista las transcripciones almacenadas.")
    pl.add_argument("--programa", help="Filtra por nombre de programa.")
    pl.set_defaults(func=_cmd_list)

    # export
    pe = sub.add_parser("export", help="Exporta a CSV y/o JSON.")
    pe.add_argument("--csv", nargs="?", const="transcripciones.csv",
                    help="Ruta del CSV de salida.")
    pe.add_argument("--json", nargs="?", const="transcripciones.json",
                    help="Ruta del JSON de salida.")
    pe.add_argument("--programa", help="Filtra por nombre de programa.")
    pe.set_defaults(func=_cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _construir_parser()
    args = parser.parse_args(argv)

    # Construimos overrides a partir de los flags globales.
    overrides = {
        "whisper": {
            "modelo": getattr(args, "whisper_modelo", None),
            "idioma": getattr(args, "idioma", None),
            "device": getattr(args, "device", None),
        },
        "rutas": {
            "data": getattr(args, "data", None),
        },
    }
    cfg = cargar_config(args.config, overrides)

    try:
        return args.func(args, cfg)
    except DependenciaFaltante as e:
        print(f"\n[Dependencia faltante] {e}", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        return 130
