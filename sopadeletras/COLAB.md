# Transcribir en Google Colab (GPU gratis)

Si no tienes tarjeta gráfica (GPU) en tu ordenador, transcribir con la CPU es
muy lento (~1 hora por capítulo). **Google Colab** te da una GPU gratis en la
nube y transcribe un capítulo en **pocos minutos**.

Colab ya trae `ffmpeg` e internet, así que puedes pegarle directamente la URL
`.m3u8` (no hace falta subir archivos de audio).

## Preparar (una vez)

1. Entra en https://colab.research.google.com (con tu cuenta de Google).
2. **Archivo → Nuevo cuaderno**.
3. **Entorno de ejecución → Cambiar tipo de entorno de ejecución → GPU (T4) →
   Guardar.** (Imprescindible: es lo que lo hace rápido.)

Pega cada bloque en una celda y ejecútalo en orden (▶️).

## Celda 1 — Instalar

```python
!pip install -q faster-whisper
```

## Celda 1b — Arreglar librerías de CUDA (si falla la GPU)

En Colab a veces falta `libcublas.so.12` y la GPU da
`RuntimeError: Library libcublas.so.12 is not found or cannot be loaded`.
Esta celda instala las librerías de NVIDIA y las enlaza donde las busca
faster-whisper. Ejecútala antes de cargar el modelo (Celda 3).

```python
!pip install -q nvidia-cublas-cu12 nvidia-cudnn-cu12
import os, glob, nvidia.cublas.lib, nvidia.cudnn.lib

destino = "/usr/lib/x86_64-linux-gnu"
carpetas = list(nvidia.cublas.lib.__path__) + list(nvidia.cudnn.lib.__path__)
for carpeta in carpetas:
    for so in glob.glob(os.path.join(carpeta, "*.so*")):
        enlace = os.path.join(destino, os.path.basename(so))
        if not os.path.lexists(enlace):
            os.symlink(so, enlace)
os.system("ldconfig")
print("Librerias de CUDA enlazadas")
```

> Plan B sin GPU: si la GPU sigue dando guerra, en la Celda 3 pon
> `device="cpu"` y `compute_type="int8"`. No necesita CUDA; va más lento que
> la GPU pero sin líos.

## Celda 2 — Guardar resultados en Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

## Celda 3 — Cargar el modelo (GPU)

```python
from faster_whisper import WhisperModel
model = WhisperModel("medium", device="cuda", compute_type="float16")
print("Modelo listo en GPU")
```

## Celda 4 — Función descargar + transcribir

> Nota: leemos el WAV a mano con `wave`+`numpy` y le pasamos el array a
> faster-whisper. Esto evita un fallo conocido en Colab
> (`TypeError: open() got an unexpected keyword argument 'metadata_errors'`)
> por incompatibilidad entre faster-whisper y la librería PyAV al decodificar.

```python
import subprocess, json, os, wave
import numpy as np

def transcribir(fuente, programa, fecha, salida_dir="/content/drive/MyDrive/sopa"):
    os.makedirs(salida_dir, exist_ok=True)
    wav = "/content/audio.wav"
    print("Descargando audio con ffmpeg...")
    subprocess.run(
        ["ffmpeg","-y","-i",fuente,"-vn","-ac","1","-ar","16000","-f","wav",wav],
        check=True
    )
    # Leemos el WAV directamente (evita el bug de PyAV con faster-whisper).
    with wave.open(wav, "rb") as w:
        frames = w.readframes(w.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    print("Transcribiendo (GPU)...")
    segmentos_gen, info = model.transcribe(audio, language="es", beam_size=5)
    segmentos, partes = [], []
    for s in segmentos_gen:
        t = s.text.strip()
        segmentos.append({"ts_inicio": round(s.start,2),
                          "ts_fin": round(s.end,2), "texto": t})
        partes.append(t)
        print(f"[{int(s.start//60):02d}:{int(s.start%60):02d}] {t}")
    data = {"programa": programa, "fecha": fecha, "fuente": fuente,
            "idioma": info.language, "texto": " ".join(partes),
            "segmentos": segmentos}
    nombre = f"{fecha}_{programa}".replace(" ", "_") + ".json"
    ruta = os.path.join(salida_dir, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nGuardado:", ruta)
    return ruta
```

## Celda 5 — Transcribir un capítulo

Saca un `.m3u8` fresco (F12 → Red → filtro `m3u8`), pégalo y ejecuta
**inmediatamente** (el token caduca en minutos):

```python
transcribir(
    "PEGA_AQUI_EL_M3U8",
    "Sopa de Letras",
    "2026-01-19",
)
```

El resultado queda en tu Drive, carpeta `sopa`, como
`2026-01-19_Sopa_de_Letras.json`. Ese JSON (texto + segmentos con timestamps)
tiene el mismo formato que el `export` de la herramienta local, y es lo que le
pasas a otra IA para extraer y analizar las preguntas.

## Para varios capítulos

Repite solo la **Celda 5** con cada URL y fecha nuevas (las celdas 1-4 no hace
falta repetirlas en la misma sesión).

## Avisos del Colab gratis

- Tiene límite de uso diario de GPU y se desconecta tras un rato inactivo.
  Para 15-20 capítulos vas sobrado, quizá en un par de sesiones.
- Si dice que no hay GPU disponible, espera un rato o vuelve más tarde.
