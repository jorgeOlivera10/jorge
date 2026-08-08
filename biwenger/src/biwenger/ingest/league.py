"""Parseo de la respuesta de liga (standings): managers y valor de equipo."""

from __future__ import annotations

from typing import Any


def parse_standings(raw: Any) -> list[dict[str, Any]]:
    """De league() -> lista de {user_id, name, team_value, points, position}."""
    body = raw.get("data", raw) if isinstance(raw, dict) else {}
    standings = body.get("standings") if isinstance(body, dict) else None
    out: list[dict[str, Any]] = []
    for s in standings or []:
        if not isinstance(s, dict):
            continue
        uid = _int(s.get("id"))
        if uid is None:
            continue
        out.append(
            {
                "user_id": uid,
                "name": s.get("name"),
                "team_value": _int(s.get("teamValue")) or 0,
                "points": _int(s.get("points")),
                "position": _int(s.get("position")),
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
