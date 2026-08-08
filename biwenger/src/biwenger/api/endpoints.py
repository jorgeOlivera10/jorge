"""URLs y constructores de endpoints de la API NO oficial de Biwenger.

⚠️  Este es el ÚNICO módulo que conoce las rutas concretas de la API. La API no
    es oficial y puede cambiar sin aviso; si algo deja de funcionar, se repara
    AQUÍ y en ningún otro sitio. El resto del código solo llama a estas funciones.

Rutas VERIFICADAS contra proyectos reales en funcionamiento (jaimebl/biwenger,
Poppeyye/biwenger_bot). Notas de autenticación por endpoint:
    - cf.biwenger.com/...  -> datos públicos de jugadores/competición (NO requiere cabeceras).
    - biwenger.as.com/...  -> endpoints de liga (requieren Authorization + X-User + X-League).

Bases:
    - cf.biwenger.com/api/v2
    - biwenger.as.com/api/v2
"""

from __future__ import annotations

# --- Bases ---
CF_BASE = "https://cf.biwenger.com/api/v2"
AS_BASE = "https://biwenger.as.com/api/v2"

COMPETITION = "la-liga"

# Campos de reports del detalle de jugador: incluye rawStats (estadísticas reales
# por partido: minutos jugados, etc.) y el match con su estado (finished/...).
_PLAYER_REPORT_FIELDS = (
    "reports(points,home,events,status(status,statusInfo),"
    "match(*,round,home,away),star,rawStats)"
)


# --- Autenticación (base biwenger.as.com) ---
def login() -> str:
    """POST {email, password} -> {data: {token, ...}} con el token Bearer."""
    return f"{AS_BASE}/auth/login"


def account() -> str:
    """GET del perfil/cuenta; expone userId y las ligas del usuario tras el login."""
    return f"{AS_BASE}/account"


# --- Datos públicos de competición / jugadores (base cf.biwenger.com, SIN cabeceras) ---
def competition_data(score: int, lang: str = "en") -> str:
    """GET de TODOS los jugadores de LaLiga para un sistema de puntuación dado."""
    return f"{CF_BASE}/competitions/{COMPETITION}/data?lang={lang}&score={score}"


def player_detail(alias: str, score: int, lang: str = "en") -> str:
    """GET del detalle de un jugador.

    Incluye:
      - reports[]: una entrada POR PARTIDO con points, rawStats (minutos, stats
        reales), events, match(status/round/home/away) y star.
      - prices: histórico diario [fechaYYMMDD, precio] -> valores de mercado.
      - fitness: forma reciente (puntos de los últimos partidos).
      - seasons, news, team, partner (enlace a Sofascore en partner['2']['url']).
    """
    fields = f"*,team,fitness,{_PLAYER_REPORT_FIELDS},prices,competition,seasons,news,partner"
    return f"{CF_BASE}/players/{COMPETITION}/{alias}?fields={fields}&score={score}&lang={lang}"


# --- Endpoints de liga (base biwenger.as.com, REQUIEREN cabeceras) ---
def league() -> str:
    """GET de la liga activa (según cabecera X-League): standings, grupo, settings.

    `standings` es la lista de managers con {id, name, teamValue, points, position}.
    """
    return f"{AS_BASE}/league?include=all&fields=*,standings,group,settings(description)"


def league_board(league_id: str, offset: int = 0, limit: int = 500) -> str:
    """GET del tablón de movimientos (fichajes, ventas, primas) — paginado.

    Fuente principal para reconstruir la economía desde el INICIO de la liga.
    Cada elemento tiene {date, type, content:[...]}, con type en:
    transfer | adminTransfer | market | roundFinished | ...
    """
    return f"{AS_BASE}/league/{league_id}/board?offset={offset}&limit={limit}"


def rounds_league() -> str:
    """GET de la clasificación por jornada (puntos de cada plantilla por ronda)."""
    return f"{AS_BASE}/rounds/league"


def user_team(user_id: str) -> str:
    """GET del equipo de un manager (el mío o el de un rival).

    Trae players(id, owner{price}), lineups(round, points, position), offers, market,
    seasons y lastPositions. `owner.price` == 0 o ausente -> jugador de plantilla inicial.
    """
    fields = (
        "*,account(id),players(id,owner),lineups(round,points,count,position),"
        "league(id,name,competition,mode,scoreID),market,seasons,offers,lastPositions"
    )
    return f"{AS_BASE}/user/{user_id}?fields={fields}"


def my_market() -> str:
    """GET del mercado/ofertas del usuario autenticado (ofertas de compra/venta)."""
    return f"{AS_BASE}/market"


def market_daily() -> str:
    """GET del mercado diario público con valores incluidos."""
    return f"{CF_BASE}/competitions/{COMPETITION}/market?interval=day&includeValues=true"
