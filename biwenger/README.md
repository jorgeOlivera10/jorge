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
| 2 | Cliente de API (login, token, cabeceras, reintentos, throttle, caché) + verificación real | ⏳ |
| 3 | Base de datos (SQLite/SQLAlchemy) + ingesta (jugadores, mercado, plantillas, tablón) | ⏳ |
| 4 | Motor económico (saldo, puja máxima) + tests | ⏳ |
| 5 | Recomendaciones (puntos esperados, chollos, puja) | ⏳ |
| 6 | Job diario idempotente + informe | ⏳ |
| — | Dashboard opcional en Streamlit | preparado, sin implementar |

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

Se irán documentando aquí `ingest`, `economy`, `recommend` y `daily` a medida que
se implementen.

---

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
