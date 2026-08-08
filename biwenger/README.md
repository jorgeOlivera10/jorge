# biwenger-analyzer

Herramienta de análisis y automatización para una liga de **Biwenger** (fantasy de LaLiga).

Ingiere a diario los datos de la liga, **reconstruye la economía de cada rival**
(saldo estimado y puja máxima a partir del tablón de movimientos) y **recomienda
a quién fichar y por cuánto pujar**, con detección de chollos.

> ⚠️ Usa la **API NO oficial** de Biwenger. Puede cambiar sin aviso. Todas las URLs
> están aisladas en `src/biwenger/api/endpoints.py` para poder repararlas en un solo sitio.

---

## Estado del proyecto (desarrollo incremental por fases)

| Fase | Contenido | Estado |
|------|-----------|--------|
| 1 | Esqueleto, config (.env), módulo de endpoints, CLI base | ✅ hecho |
| 2 | Cliente de API (login, token, cabeceras, reintentos, throttle, caché) + `verify` | ✅ hecho |
| 3 | Base de datos (SQLite/SQLAlchemy) + ingesta idempotente (tablón, liga, jugadores) | ✅ hecho |
| 4 | Motor económico (saldo, puja máxima) + Pain tracker (€ real) + tests | ✅ hecho |
| 5 | Recomendaciones (puntos esperados, chollos, sugerencia de puja) | ✅ hecho |
| 6 | Job diario idempotente + informe en Markdown | ✅ hecho |
| — | Dashboard en Streamlit (con vista móvil) | ✅ hecho |

**El código está completo.** Lo único que queda es tu parte: rellenar `.env` con
tus credenciales/cabeceras reales, verificar los IDs de `score` en local
(`biwenger verify`) y ejecutar. Ver "Setup" y "Cómo capturar mis cabeceras".

---

## Requisitos

- Python 3.10+
- Una cuenta de Biwenger y una liga en marcha.

## Setup

```bash
# 1. Entra en la carpeta del proyecto
cd biwenger

# 2. Crea y activa un entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instala en modo editable (con extras de desarrollo)
pip install -e ".[dev]"

# 4. Copia la plantilla de configuración y rellénala
cp .env.example .env
#   ...edita .env con tu editor favorito...

# 5. Comprueba que la configuración se carga bien
biwenger config
```

El comando `biwenger config` muestra la configuración cargada (ocultando las
credenciales) y te avisa de qué campos faltan por rellenar en tu `.env`.

---

## Cómo capturar mis cabeceras (X-User, X-League, X-Version)

Biwenger autentica cada petición con tres cabeceras que hay que capturar **una vez**
desde el navegador. El token Bearer se obtiene automáticamente al hacer login con tu
email/contraseña; las cabeceras identifican tu usuario, tu liga y la versión del cliente.

1. Abre **https://biwenger.as.com** en el navegador e **inicia sesión** en tu liga.
2. Abre las **DevTools** con `F12` (o clic derecho → *Inspeccionar*).
3. Ve a la pestaña **Network** (Red) y marca el filtro **Fetch/XHR**.
4. **Recarga** la página (`F5`). Verás muchas peticiones.
5. Pincha en cualquier petición a **`cf.biwenger.com`** o **`biwenger.as.com`**.
6. En **Request Headers** (Cabeceras de solicitud) localiza y copia:
   - **`X-User`**    → va a `BIWENGER_USER_ID` en tu `.env`
   - **`X-League`**  → va a `BIWENGER_LEAGUE_ID`
   - **`X-Version`** → va a `BIWENGER_VERSION`
7. Pega esos valores en tu `.env`. (El `Authorization: Bearer ...` no hace falta
   copiarlo: la herramienta hace login por ti.)

> Tus credenciales y cabeceras viven **solo** en `.env`, que está en `.gitignore`
> y nunca se sube al repositorio.

---

## Comandos de la CLI

De momento (Fase 1):

| Comando | Descripción |
|---------|-------------|
| `biwenger version` | Muestra la versión de la herramienta. |
| `biwenger config`  | Muestra la configuración cargada y qué falta en `.env`. |
| `biwenger verify`  | Llamada **real** al endpoint público de LaLiga para verificar/ajustar los IDs de `score`. Añade `--login` para probar también las credenciales. |
| `biwenger init-db` | Crea la base de datos SQLite y su esquema (idempotente). |
| `biwenger ingest`  | **Ingesta diaria**: login → tablón completo + standings, reconstruye la economía de cada manager y el Pain tracker, y guarda todo en la BD. Idempotente (solo añade lo nuevo). |
| `biwenger economy` | Muestra la última **economía estimada** por manager: saldo, valor de equipo, **puja máxima** y total. |
| `biwenger pain`    | Muestra el **Pain tracker**: marcador de dinero **real** (€) por manager según los castigos de jornada. |
| `biwenger squads` | Lista las **plantillas** de los managers (jugador, posición, equipo, valor y lo que pagó). `--user <nombre>` para uno solo. |
| `biwenger team` | **Tu plantilla** con estado físico, si va a jugar, **rendimiento esperado** (temp. actual o pasada), tendencia de precio y **alerta de VENDER** si hay lesión/noticia. |
| `biwenger alerts` | Solo tus jugadores con **lesión/duda/sanción o noticia** → señales de venta inmediata. |
| `biwenger market` | Jugadores en el **mercado de la banca** hoy, con **estado, si es titular, noticia**, valor y **puja sugerida**. `--no-bank-only` para incluir los de rivales; `--no-scout` para no descargar fichas. |
| `biwenger recommend` | **Chollos** (mejor relación puntos/precio) y **sugerencia de puja**. Opciones: `--top N`, `--max-price`, `--position 1..4`, `--min-games`, y `--player <id>` para una sugerencia de puja concreta (cruza tu puja máxima con el techo de tus rivales). |
| `biwenger daily`   | **Job diario**: login → ingesta idempotente → deja un **informe** en `reports/AAAA-MM-DD.md` y un **dashboard HTML** en `reports/dashboard.html`. |
| `biwenger html`    | Genera `reports/dashboard.html` (un **único archivo**, sin servidor) y lo abre. Ábrelo con doble clic o envíatelo al móvil para verlo en cualquier sitio. |

### Automatizar el job diario

`biwenger daily` es idempotente (procesa solo lo nuevo), así que puedes programarlo:

```bash
# cron (Linux/Mac): todos los días a las 09:00
0 9 * * *  cd /ruta/a/biwenger && ./.venv/bin/biwenger daily >> logs/daily.log 2>&1
```

En Windows usa el **Programador de tareas** apuntando a `.\.venv\Scripts\biwenger.exe daily`.

Se irán documentando aquí `ingest`, `economy`, `recommend` y `daily` a medida que
se implementen.

> **Nota sobre `verify`:** compara el nº de jugadores y los puntos totales entre
> Sofascore y Picas del AS. Si los totales **difieren**, los IDs de `score` son
> correctos. Si te da error 403/red en un entorno con proxy restrictivo, ejecútalo
> en tu máquina local:
> ```bash
> biwenger verify
> ```

---

## Dashboard (y verlo en el móvil)

Un panel visual con pestañas (Economía, Mi equipo, Chollos, Plantillas, Pain) que
lee la base de datos que genera `biwenger daily`.

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/streamlit_app.py
```

Al arrancar, Streamlit muestra dos direcciones:

```
Local URL:   http://localhost:8501
Network URL: http://192.168.x.x:8501   ← ábrela en el MÓVIL
```

**Para verlo en el móvil:** con el teléfono en el **mismo WiFi** que el PC, abre la
**Network URL** en el navegador del móvil. El diseño es responsive.

> El dashboard muestra lo último que ingirió `biwenger daily`; ejecútalo para
> refrescar los datos (o programa el job diario). Botón "🔄 Recargar" para releer la BD.

### Verlo en cualquier sitio (lo más fácil)

En vez del servidor Streamlit, `biwenger daily` (o `biwenger html`) genera un
**único archivo** `reports/dashboard.html`, sin servidor ni instalación:

- **En el PC:** doble clic → se abre en el navegador.
- **En el móvil, desde cualquier sitio:** guarda ese `dashboard.html` en tu
  **Google Drive / iCloud** (o mándatelo por WhatsApp/Telegram) y ábrelo en el
  móvil. Es privado (solo tú lo tienes) y funciona sin PC encendido.
- **Siempre online y automático (sin tocar nada):** un **GitHub Action** puede
  ejecutar el job cada día y publicar el dashboard en **GitHub Pages** (URL fija
  para el móvil). Ojo: Pages es **público**; pregúntame y te lo monto (o te dejo
  una variante privada).

## Sistemas de puntuación

La liga usa **Sofascore** y **Picas del AS**. La API selecciona el sistema con el
parámetro `?score=<id>`. Los IDs se configuran en `.env`
(`BIWENGER_SCORE_SOFASCORE`, `BIWENGER_SCORE_AS`) y se **verifican contra la API**
en la Fase 2 por si cambian.

---

## Aviso sobre la estimación económica

El saldo y la puja máxima de cada rival son una **ESTIMACIÓN** reconstruida desde el
tablón de movimientos:

```
saldo_estimado = presupuesto_inicial + ventas + primas − fichajes
puja_maxima    = saldo_estimado + 0.25 × valor_de_equipo
```

Fuentes de error conocidas (documentadas para no fiarse ciegamente):

- **Primas** por objetivos que no siempre aparecen en el tablón.
- **Cláusulas / salarios** si tu liga los tiene activados.
- Managers que **guardan liquidez** a propósito o que ya tienen ofertas pendientes.
- El coeficiente `0.25 × valor_equipo` es un **supuesto de reglas** de Biwenger.

Trátalo como una guía, no como una cifra exacta.

---

## Desarrollo

```bash
pip install -e ".[dev]"
pytest            # ejecuta los tests (motor económico y parseo del tablón)
ruff check src    # linting
```
