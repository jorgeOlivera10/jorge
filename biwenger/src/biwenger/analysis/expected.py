"""Cálculo de 'puntos esperados' y ratios de valor de los jugadores.

Funciones PURAS sobre dicts/objetos normalizados (sin BD). Documentado y
sencillo a propósito: es una heurística transparente, no una caja negra.

Idea:
  - points_per_match = puntos_totales / partidos_jugados
  - reliability      = fiabilidad de titularidad (partidos jugados / jornadas
                       disputadas), penaliza a los que juegan poco.
  - momentum         = tendencia del precio (priceIncrement / precio), pequeño
                       empujón: un jugador cuyo valor sube suele estar "on fire".
  - expected_points  = points_per_match * reliability * (1 + momentum acotado)
  - value_ratio      = expected_points por cada millón de precio  → detecta chollos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POSITION_NAMES = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}


@dataclass
class PlayerValue:
    player_id: int
    name: str | None
    position: int | None
    team_name: str | None
    price: int
    price_increment: int
    played: int
    points_per_match: float
    reliability: float
    momentum: float
    expected_points: float
    value_ratio: float          # puntos esperados por millón
    status: str | None

    @property
    def position_name(self) -> str:
        return POSITION_NAMES.get(self.position or 0, "?")


def _num(v: Any, default: float = 0.0) -> float:
    return float(v) if isinstance(v, (int, float)) else default


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_player_value(p: dict[str, Any] | Any, rounds_played: int | None) -> PlayerValue:
    """Calcula las métricas de un jugador. Acepta dict o un objeto con atributos."""
    get = (lambda k: p.get(k)) if isinstance(p, dict) else (lambda k: getattr(p, k, None))

    price = int(_num(get("price")))
    price_inc = int(_num(get("price_increment")))
    total_points = _num(get("total_points"))
    played = int(_num(get("played")))
    # Si no hay 'played' agregado, intentamos derivarlo de home+away.
    if played == 0:
        played = int(_num(get("played_home")) + _num(get("played_away")))
        if total_points == 0:
            total_points = _num(get("points_home")) + _num(get("points_away"))

    ppm = (total_points / played) if played > 0 else 0.0
    reliability = _clamp(played / rounds_played, 0.0, 1.0) if rounds_played else 1.0
    momentum = _clamp(price_inc / price, -0.15, 0.15) if price > 0 else 0.0
    expected = ppm * reliability * (1 + momentum)
    value_ratio = (expected / (price / 1_000_000)) if price > 0 else 0.0

    team = get("team_name")
    return PlayerValue(
        player_id=int(_num(get("id") if isinstance(p, dict) else get("id"))) if get("id") is not None else int(_num(get("player_id"))),
        name=get("name"),
        position=get("position"),
        team_name=team,
        price=price,
        price_increment=price_inc,
        played=played,
        points_per_match=round(ppm, 2),
        reliability=round(reliability, 2),
        momentum=round(momentum, 3),
        expected_points=round(expected, 2),
        value_ratio=round(value_ratio, 3),
        status=get("status"),
    )


def analyze_players(players: list[dict[str, Any] | Any]) -> list[PlayerValue]:
    """Calcula métricas para una lista de jugadores.

    `rounds_played` se estima como el máximo de partidos jugados por cualquier
    jugador (proxy del nº de jornadas disputadas hasta la fecha).
    """
    def _played(p: Any) -> int:
        get = (lambda k: p.get(k)) if isinstance(p, dict) else (lambda k: getattr(p, k, None))
        pl = int(_num(get("played")))
        if pl == 0:
            pl = int(_num(get("played_home")) + _num(get("played_away")))
        return pl

    rounds_played = max((_played(p) for p in players), default=0) or None
    return [compute_player_value(p, rounds_played) for p in players]
