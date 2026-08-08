"""Parseo de la ficha DETALLADA de un jugador (scouting).

De aquí salen las cosas que pides: estado físico (lesión/duda/sanción), noticias,
forma reciente, minutos y rendimiento de la temporada pasada. Todo defensivo:
la API es no oficial y puede omitir campos.
"""

from __future__ import annotations

from datetime import date, datetime
from statistics import mean
from typing import Any

# Estados de disponibilidad conocidos y si implican riesgo de no jugar.
RISK_STATUSES = {"injured", "doubt", "doubtful", "suspended", "sanctioned"}


def parse_player_detail(detail: Any) -> dict[str, Any]:
    """De player_detail -> dict con estado, noticias, forma y temporada pasada."""
    body = detail.get("data", detail) if isinstance(detail, dict) else {}

    status = body.get("status")
    status_info = body.get("statusInfo") if isinstance(body.get("statusInfo"), str) else None

    # Noticias (lista de {date, title, content})
    news: list[dict[str, Any]] = []
    for n in body.get("news") or []:
        if not isinstance(n, dict):
            continue
        d = _epoch_to_date(n.get("date"))
        title = n.get("title") or n.get("headline")
        if title:
            news.append({"date": d, "title": str(title)[:300],
                         "content": (str(n.get("content"))[:2000] if n.get("content") else None)})
    news.sort(key=lambda x: (x["date"] or date.min), reverse=True)

    # Forma reciente: media de los valores numéricos de fitness.
    fitness_vals = [v for v in (body.get("fitness") or []) if isinstance(v, (int, float))]
    fitness_avg = round(mean(fitness_vals), 2) if fitness_vals else None

    # Temporada pasada: la más reciente de 'seasons' con juegos.
    last_season = _last_season(body.get("seasons"))

    return {
        "player_id": _int(body.get("id")),
        "slug": body.get("slug"),
        "status": status,
        "status_info": status_info,
        "is_risky": (status in RISK_STATUSES) if status else False,
        "news": news,
        "news_title": news[0]["title"] if news else None,
        "news_date": news[0]["date"] if news else None,
        "fitness_avg": fitness_avg,
        "last_season_points": last_season.get("points"),
        "last_season_games": last_season.get("games"),
    }


def _last_season(seasons: Any) -> dict[str, int | None]:
    best: dict[str, int | None] = {"points": None, "games": None}
    if not isinstance(seasons, list):
        return best
    # Escogemos la temporada con más partidos (heurística: la última completa).
    candidates = []
    for s in seasons:
        if not isinstance(s, dict):
            continue
        games = _int(s.get("games"))
        points = _int(s.get("points"))
        if games:
            candidates.append((games, points))
    if candidates:
        candidates.sort(reverse=True)
        best = {"games": candidates[0][0], "points": candidates[0][1]}
    return best


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
