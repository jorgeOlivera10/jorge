"""URLs y constructores de endpoints de la API NO oficial de Biwenger.

⚠️  Este es el ÚNICO módulo que conoce las rutas concretas de la API. La API no
    es oficial y puede cambiar sin aviso; si algo deja de funcionar, se repara
    AQUÍ y en ningún otro sitio. El resto del código solo llama a estas funciones.

Bases conocidas:
    - cf.biwenger.com/api/v2 : datos de competición, jugadores y mercado.
    - biwenger.as.com/api/v2 : login y endpoints de liga (mi equipo, rivales, tablón).

Los endpoints marcados con "TODO verificar" deben confirmarse en la Fase 2 con
una llamada real y ajustarse si difieren.
"""

from __future__ import annotations

# --- Bases ---
CF_BASE = "https://cf.biwenger.com/api/v2"
AS_BASE = "https://biwenger.as.com/api/v2"

COMPETITION = "la-liga"


# --- Autenticación ---
def login() -> str:
    """POST con {email, password} -> devuelve token Bearer."""
    return f"{AS_BASE}/auth/login"


def account() -> str:
    """GET del perfil/cuenta; útil para descubrir userId y ligas tras el login."""
    return f"{AS_BASE}/account"


# --- Datos de competición / jugadores (base pública cf.biwenger.com) ---
def competition_data(score: int, lang: str = "en") -> str:
    """GET de TODOS los jugadores de LaLiga para un sistema de puntuación dado."""
    return f"{CF_BASE}/competitions/{COMPETITION}/data?lang={lang}&score={score}"


def player_detail(alias: str, score: int) -> str:
    """GET del detalle de un jugador (puntos por jornada, precios, seasons, news...)."""
    fields = "*,team,fitness,reports(points,home,events,status,match),prices,seasons,news"
    return f"{CF_BASE}/players/{COMPETITION}/{alias}?fields={fields}&score={score}"


def market_daily() -> str:
    """GET del mercado del día con valores incluidos."""
    return f"{CF_BASE}/competitions/{COMPETITION}/market?interval=day&includeValues=true"


# --- Endpoints de liga (base biwenger.as.com) ---
# TODO verificar en Fase 2: las rutas exactas de liga dependen del leagueId y
# pueden requerir las cabeceras X-User / X-League / X-Version.
def league(league_id: str) -> str:
    """GET de la liga: incluye usuarios/managers y (según fields) sus plantillas."""
    return f"{AS_BASE}/league/{league_id}?fields=*,standings,users(*)"


def league_board(league_id: str, offset: int = 0, limit: int = 50) -> str:
    """GET del tablón de movimientos (fichajes, ventas, primas) — paginado.

    Fuente principal para reconstruir la economía desde el INICIO de la liga.
    TODO verificar: nombre del recurso ('board'/'news'/'notifications') y los
    parámetros de paginación reales.
    """
    return f"{AS_BASE}/league/{league_id}/board?offset={offset}&limit={limit}"


def user_squad(league_id: str, user_id: str) -> str:
    """GET de la plantilla de un manager (la mía o la de un rival)."""
    return f"{AS_BASE}/user/{user_id}?fields=*,players(*)&league={league_id}"
