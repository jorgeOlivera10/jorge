"""Parseo de jugadores, puntos por jornada y valores de mercado.

Funciones PURAS: transforman las respuestas de la API en dicts normalizados
listos para persistir. La red y la BD viven fuera (client.py / store.py).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from biwenger.api.parse import extract_players


def parse_competition_players(raw: Any) -> list[dict[str, Any]]:
    """De competition_data -> lista de dicts de Player (maestro + precio actual)."""
    out: list[dict[str, Any]] = []
    for p in extract_players(raw):
        team = p.get("team")
        team_id = team.get("id") if isinstance(team, dict) else p.get("teamID")
        out.append(
            {
                "id": _int(p.get("id")),
                "name": p.get("name"),
                "slug": p.get("slug"),
                "team_id": _int(team_id),
                "team_name": team.get("name") if isinstance(team, dict) else None,
                "position": _int(p.get("position")),
                "price": _int(p.get("price")),
                "price_increment": _int(p.get("priceIncrement")),
                "status": p.get("status"),
                "total_points": _int(p.get("points")),
                "played": _int(p.get("played")),
                "points_home": _int(p.get("pointsHome")),
                "played_home": _int(p.get("playedHome")),
                "points_away": _int(p.get("pointsAway")),
                "played_away": _int(p.get("playedAway")),
                "updated_at": datetime.utcnow(),
            }
        )
    return [p for p in out if p["id"] is not None]


def parse_player_reports(detail: Any, score_system: str) -> list[dict[str, Any]]:
    """De player_detail.reports[] -> puntos POR JORNADA con minutos y stats reales."""
    body = detail.get("data", detail) if isinstance(detail, dict) else {}
    player_id = _int(body.get("id"))
    reports = body.get("reports") or []
    out: list[dict[str, Any]] = []
    for rep in reports:
        if not isinstance(rep, dict):
            continue
        match = rep.get("match") if isinstance(rep.get("match"), dict) else {}
        rnd = match.get("round") if isinstance(match.get("round"), dict) else {}
        raw_stats = rep.get("rawStats") if isinstance(rep.get("rawStats"), dict) else {}
        out.append(
            {
                "player_id": player_id,
                "round": _int(rnd.get("id")) or _round_from_name(rnd.get("name")),
                "score_system": score_system,
                "points": _int(rep.get("points")) or 0,
                "minutes": _int(raw_stats.get("minutesPlayed")),
                "home": bool(rep.get("home")) if rep.get("home") is not None else None,
                "match_status": match.get("status"),
                "star": bool(rep.get("star")) if rep.get("star") is not None else None,
            }
        )
    return [r for r in out if r["player_id"] is not None and r["round"] is not None]


def parse_player_prices(detail: Any) -> list[dict[str, Any]]:
    """De player_detail.prices[] ([YYMMDD, precio]) -> valores de mercado por fecha."""
    body = detail.get("data", detail) if isinstance(detail, dict) else {}
    player_id = _int(body.get("id"))
    out: list[dict[str, Any]] = []
    for pair in body.get("prices") or []:
        if not (isinstance(pair, (list, tuple)) and len(pair) >= 2):
            continue
        d = _yymmdd_to_date(pair[0])
        price = _int(pair[1])
        if d is not None and price is not None and player_id is not None:
            out.append({"player_id": player_id, "date": d, "price": price})
    return out


# --- helpers ---
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


def _round_from_name(name: Any) -> int | None:
    if isinstance(name, str):
        for tok in name.replace("ª", " ").split():
            if tok.isdigit():
                return int(tok)
    return None


def _yymmdd_to_date(val: Any) -> date | None:
    s = str(val)
    if len(s) == 6 and s.isdigit():
        try:
            return datetime.strptime(s, "%y%m%d").date()
        except ValueError:
            return None
    return None
