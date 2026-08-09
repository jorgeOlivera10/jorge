"""Normalización defensiva de las respuestas de la API.

La API no es oficial y su forma puede variar. Estas funciones aíslan el "shape"
del JSON para que el resto del código trabaje con estructuras estables. Si la
API cambia, se ajusta aquí (y en endpoints.py).
"""

from __future__ import annotations

from typing import Any


def unwrap(raw: Any) -> Any:
    """Devuelve el cuerpo útil, quitando el envoltorio {status, data} si existe."""
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], (dict, list)):
        return raw["data"]
    return raw


def extract_players(raw: Any) -> list[dict[str, Any]]:
    """Extrae la lista de jugadores de la respuesta de competition_data.

    Soporta tanto `players` como dict {id: {...}} como lista [ {...} ].
    Devuelve una lista de dicts con, al menos, id/name/points/price cuando existen.
    """
    body = unwrap(raw)
    players_raw: Any = None
    if isinstance(body, dict):
        players_raw = body.get("players")
    if players_raw is None and isinstance(raw, dict):
        players_raw = raw.get("players")
    if players_raw is None:
        return []

    if isinstance(players_raw, dict):
        items = list(players_raw.values())
    elif isinstance(players_raw, list):
        items = players_raw
    else:
        return []

    return [p for p in items if isinstance(p, dict)]


def player_points(player: dict[str, Any]) -> int:
    """Puntos totales de temporada del jugador para el score consultado."""
    for key in ("points", "totalPoints", "pointsTotal"):
        val = player.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    return 0
