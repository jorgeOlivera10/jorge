"""Parseo del mercado del día (jugadores en venta en la liga).

El endpoint /market (biwenger.as.com) devuelve, según versión, algo como:
    {"data": {"sales": [{"price": ..., "until": ..., "user": {"id":..}|None,
                          "player": <id|{"id":..}>}, ...],
              "offers": [...]}}
Parseamos de forma DEFENSIVA porque la API es no oficial: si algún campo no
está donde esperamos, se ignora ese registro en vez de romper.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_market(raw: Any) -> list[dict[str, Any]]:
    """De /market -> lista de {player_id, price, seller_id, until} de jugadores en venta."""
    body = raw.get("data", raw) if isinstance(raw, dict) else {}
    sales = None
    if isinstance(body, dict):
        # varios nombres posibles según versión de la API
        for key in ("sales", "market", "players"):
            if isinstance(body.get(key), list):
                sales = body[key]
                break
    if sales is None:
        return []

    out: list[dict[str, Any]] = []
    for s in sales:
        if not isinstance(s, dict):
            continue
        player = s.get("player")
        if isinstance(player, dict):
            player_id = _int(player.get("id"))
        else:
            player_id = _int(player)
        if player_id is None:
            continue
        seller = s.get("user") if isinstance(s.get("user"), dict) else None
        seller_id = _int(seller.get("id")) if seller else _int(s.get("userID"))
        out.append(
            {
                "player_id": player_id,
                "price": _int(s.get("price")),
                "seller_id": seller_id,          # None = jugador de la banca
                "until": _epoch_to_date(s.get("until") or s.get("date")),
            }
        )
    return out


def _int(val: Any) -> int | None:
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str) and val.lstrip("-").isdigit():
        return int(val)
    return None


def _epoch_to_date(val: Any) -> date | None:
    try:
        return datetime.fromtimestamp(int(val)).date()
    except (TypeError, ValueError, OSError):
        return None
