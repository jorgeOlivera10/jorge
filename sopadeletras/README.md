# Sopa de Letras Extractor

Herramienta de línea de comandos **100% local y gratuita** (sin APIs de pago,
sin claves, sin suscripciones) para transcribir capítulos del concurso
**"Sopa de Letras"** de Aragón TV (Aragón Play) y guardarlos en una base de
datos consultable y exportable.

El presentador lee las preguntas en voz alta y las respuestas también se dicen
en el audio. Esta herramienta se encarga solo de **transcribir y almacenar**;
el trabajo de aislar las preguntas, responderlas, clasificarlas por tema y
generar una app tipo trivial se delega a otra IA, a la que le pasas la
exportación (`export`).

## Pipeline

```
entrada (URL .m3u8/.mp4 o archivo local)
      │  ffmpeg
      ▼
audio WAV mono 16 kHz          (cacheado en data/audio/)
      │  faster-whisper
      ▼
transcripción + timestamps     (cacheado en data/transcripts/, JSON)
      │
      ▼
SQLite (data/sopadeletras.db)  →  export CSV / JSON  →  otra IA
```

Cada etapa es **idempotente y cacheada**: reprocesar la misma entrada no
repite el trabajo (usa `--force` para rehacer una etapa).

## Requisitos

- **Python 3.10+**
- **ffmpeg** (binario del sistema, no se instala por pip)
- **faster-whisper** y **PyYAML** (se instalan por pip)
- **yt-dlp** (opcional): solo hace falta si le pasas la **URL de una página web**
  en vez de un `.m3u8` o un archivo. Se instala con `pip install -U yt-dlp`.

> La herramienta **no instala nada por su cuenta**: si falta ffmpeg,
> faster-whisper o yt-dlp (cuando lo necesita), te avisa con instrucciones
> claras y se detiene.

## Instalación

```bash
# 1) Dependencias de Python
pip install -r requirements.txt

# 2) ffmpeg (elige según tu sistema)
sudo apt install ffmpeg        # Debian/Ubuntu
brew install ffmpeg            # macOS
# Windows: https://ffmpeg.org/download.html

# 3) (opcional) configuración propia
cp config.yaml.example config.yaml
```

La **primera** transcripción descarga el modelo de whisper (por defecto
`medium`) una sola vez; luego queda en caché local y todo funciona offline.

## Dos formas de pasar el vídeo

### Forma fácil (recomendada): la URL de la página + yt-dlp

Si tienes `yt-dlp` instalado (`pip install -U yt-dlp`), puedes pasar
directamente la **URL de la página** del capítulo, sin tener que sacar el
`.m3u8` a mano:

```bash
python -m sdl ingest \
  --fuente "https://www.aragonplay.es/watch/media/sopa-de-letras-2026-01-19" \
  --programa "Sopa de Letras" --fecha 2026-01-19
```

La herramienta detecta que es una página web y usa yt-dlp para descargar el
vídeo automáticamente. **Sin F12, sin tokens que caducan.**

Si el vídeo requiere haber iniciado sesión, añade `--navegador chrome` (o
`firefox`, `edge`...) para que yt-dlp use las cookies de tu navegador:

```bash
python -m sdl ingest --fuente "https://www.aragonplay.es/watch/..." \
  --programa "Sopa de Letras" --fecha 2026-01-19 --navegador chrome
```

### Forma manual: la URL `.m3u8`

Si no quieres usar yt-dlp, o yt-dlp no soporta el vídeo, puedes copiar la URL
del stream a mano desde el navegador:

1. Abre el capítulo en la web de **Aragón Play** en tu navegador.
2. Pulsa **F12** para abrir las **herramientas de desarrollador**.
3. Ve a la pestaña **Red** (Network).
4. En el filtro de esa pestaña, escribe **`m3u8`**.
5. Dale al **play** del vídeo (si ya estaba reproduciéndose, recarga la página).
6. Aparecerá una petición cuyo nombre acaba en **`.m3u8`**. Haz clic derecho
   sobre ella → **Copiar** → **Copiar URL**.
7. Esa es la URL que le pasas a `--fuente`.

> ⚠️ Estas URLs **suelen caducar** al cabo de un rato. Úsala cuanto antes; si
> ffmpeg da error de descarga, vuelve a copiarla. Como alternativa, puedes
> descargar el vídeo a un `.mp4` con otra herramienta y pasar la ruta local.

## Uso

### Procesar un capítulo

```bash
python -m sdl ingest \
  --fuente "https://.../playlist.m3u8" \
  --programa "Sopa de Letras" \
  --fecha 2026-09-13
```

También vale un archivo local:

```bash
python -m sdl ingest --fuente /ruta/capitulo.mp4 \
  --programa "Sopa de Letras" --fecha 2026-09-13
```

Flags útiles: `--force` (rehace aunque haya caché), `--dry-run` (transcribe
pero no escribe en la BD).

### Procesar varios capítulos (cola)

Crea un CSV con cabecera `fuente,programa,fecha`:

```csv
fuente,programa,fecha
https://.../cap1.m3u8,Sopa de Letras,2026-09-11
/ruta/cap2.mp4,Sopa de Letras,2026-09-12
```

```bash
python -m sdl ingest-batch capitulos.csv
```

Si un capítulo falla, se registra el error y la cola continúa con el siguiente.

### Listar lo almacenado

```bash
python -m sdl list
python -m sdl list --programa "Sopa de Letras"
```

### Exportar para otra IA

```bash
python -m sdl export                       # crea transcripciones.csv y .json
python -m sdl export --json salida.json    # solo JSON
python -m sdl export --csv salida.csv      # solo CSV
```

El **JSON** incluye el texto completo y los segmentos con timestamps
(`ts_inicio`, `ts_fin`), ideal para pasárselo a otra IA que aísle las
preguntas y genere el resto. El **CSV** trae una fila por capítulo con el
texto completo.

## Configuración

Todo se puede ajustar con `config.yaml` (copia `config.yaml.example`) o con
flags globales:

| Ajuste            | config.yaml            | flag                  | por defecto |
|-------------------|------------------------|-----------------------|-------------|
| Modelo whisper    | `whisper.modelo`       | `--whisper-modelo`    | `medium`    |
| Idioma            | `whisper.idioma`       | `--idioma`            | `es`        |
| Dispositivo       | `whisper.device`       | `--device`            | `auto`      |
| Carpeta de datos  | `rutas.data`           | `--data`              | `data`      |

Ejemplo (modelo más rápido en CPU):

```bash
python -m sdl --whisper-modelo small --device cpu ingest \
  --fuente cap.mp4 --programa "Sopa de Letras" --fecha 2026-09-13
```

## Esquema de la base de datos

Tabla `transcripciones`:

| Columna      | Tipo | Descripción                                   |
|--------------|------|-----------------------------------------------|
| `id`         | INT  | Clave primaria                                |
| `programa`   | TEXT | Nombre del programa                           |
| `fecha`      | TEXT | `YYYY-MM-DD`                                   |
| `texto`      | TEXT | Transcripción completa                        |
| `segmentos`  | TEXT | JSON: `[{ts_inicio, ts_fin, texto}, ...]`     |
| `fuente`     | TEXT | URL o ruta original                           |
| `idioma`     | TEXT | Idioma detectado                              |
| `created_at` | TEXT | Fecha de inserción                            |

Dedupe por `UNIQUE(programa, fecha)`: reprocesar el mismo capítulo no crea
filas duplicadas.

## Estructura del proyecto

```
sopadeletras/
├── README.md
├── requirements.txt
├── config.yaml.example
└── sdl/
    ├── cli.py          # comandos: ingest / ingest-batch / list / export
    ├── config.py       # config.yaml + defaults + overrides
    ├── deps.py         # comprobación de ffmpeg / faster-whisper
    ├── audio.py        # etapa 2: ffmpeg -> WAV mono 16 kHz
    ├── transcribe.py   # etapa 3: faster-whisper -> JSON
    ├── storage.py      # etapa 5: SQLite + dedupe
    └── utils.py        # slugs, validación de fecha, etc.
```

## Notas

- No se incluye ninguna clave de API ni servicio de pago en ningún sitio.
- Todo el procesamiento ocurre en tu máquina.
