"""Parseo de la plantilla de un manager (user_team)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_user_team(raw: Any) -> dict[str, Any]:
    """De user_team -> {'user': {...}, 'squad': [{player_id, buy_price}, ...]}.

    owner.price == 0 o ausente indica jugador de plantilla inicial (no comprado).
    """
    body = raw.get("data", raw) if isinstance(raw, dict) else {}
    user = {
        "id": _int(body.get("id")),
        "name": body.get("name"),
        "join_date": _epoch_to_date(body.get("joinDate")),
    }
    squad: list[dict[str, Any]] = []
    for p in body.get("players") or []:
        if not isinstance(p, dict):
            continue
        pid = _int(p.get("id"))
        if pid is None:
            continue
        owner = p.get("owner") if isinstance(p.get("owner"), dict) else {}
        squad.append({"player_id": pid, "buy_price": _int(owner.get("price"))})
    return {"user": user, "squad": squad}


def _int(val: Any) -> int | None:
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.lstrip("-").isdigit():
        return int(val)
    return None


def _epoch_to_date(val: Any) -> date | None:
    try:
        return datetime.fromtimestamp(int(val)).date()
    except (TypeError, ValueError, OSError):
        return None
