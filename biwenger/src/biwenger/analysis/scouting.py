"""Veredicto por jugador: ¿va a jugar?, ¿rinde?, ¿hay que venderlo ya?

Combina el estado físico, las noticias, la forma y el rendimiento de la
temporada pasada para dar una lectura rápida, incluso al inicio de liga cuando
todavía no hay puntos esta temporada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STATUS_LABEL = {
    "ok": "OK",
    "injured": "🚑 LESIONADO",
    "doubt": "⚠️ DUDA",
    "doubtful": "⚠️ DUDA",
    "suspended": "🚫 SANCIONADO",
    "sanctioned": "🚫 SANCIONADO",
    "unknown": "¿?",
}
RISK = {"injured", "doubt", "doubtful", "suspended", "sanctioned"}
_INJURY_WORDS = ("lesion", "rotura", "baja", "operado", "molestias", "duda", "sancion")


@dataclass
class PlayerOutlook:
    player_id: int
    name: str | None
    position: int | None
    team_name: str | None
    price: int
    price_increment: int
    status: str | None
    status_label: str
    will_play: str            # Titular / Rotación / Poco habitual / No disponible
    expected_ppg: float | None  # puntos esperados por partido (o de la temp. pasada)
    basis: str                # "esta temporada" | "temp. pasada" | "sin datos"
    status_info: str | None   # motivo del estado (lesión/duda), específico del jugador
    news_title: str | None    # noticia del jugador (ya filtrada; puede ser None)
    note: str                 # texto a mostrar como 'nota' (estado > noticia)
    sell_now: bool            # alerta de venta inmediata
    reason: str


def _num(v: Any) -> float:
    return float(v) if isinstance(v, (int, float)) else 0.0


def player_outlook(p: Any) -> PlayerOutlook:
    """Calcula el veredicto de un Player (ORM u objeto con esos atributos)."""
    g = (lambda k: getattr(p, k, None))
    status = g("status")
    risky = status in RISK

    played = int(_num(g("played")))
    total_points = _num(g("total_points"))
    ls_games = int(_num(g("last_season_games")))
    ls_points = _num(g("last_season_points"))

    if played > 0:
        expected = round(total_points / played, 2)
        basis = "esta temporada"
    elif ls_games > 0:
        expected = round(ls_points / ls_games, 2)
        basis = "temp. pasada"
    else:
        expected = None
        basis = "sin datos"

    # ¿Va a jugar? Al inicio de liga usamos los partidos de la temporada pasada
    # como proxy de titularidad, más el estado físico.
    games_ref = played if played > 0 else ls_games
    if risky:
        will_play = "No disponible"
    elif games_ref >= 28:
        will_play = "Titular"
    elif games_ref >= 15:
        will_play = "Rotación"
    elif games_ref > 0:
        will_play = "Poco habitual"
    else:
        will_play = "Sin histórico"

    status_info = g("status_info")
    news = g("news_title")
    # Alerta de venta: por estado (lesión/duda/sanción) o por el motivo del estado.
    # NO usamos el feed de noticias genérico para esto (no es del jugador).
    sell_now = risky or bool(status_info and any(w in status_info.lower() for w in _INJURY_WORDS))

    # 'Nota' a mostrar: el motivo del estado es lo específico del jugador; si no
    # hay, mostramos la noticia ya filtrada (solo se guardan las que le mencionan).
    note = status_info or (news or "")

    if sell_now:
        reason = f"{STATUS_LABEL.get(status, status or '')}" + (f" · {status_info}" if status_info else "")
    elif expected is not None:
        reason = f"~{expected} pts/partido ({basis}); {will_play.lower()}"
    else:
        reason = "sin histórico de rendimiento"

    return PlayerOutlook(
        player_id=int(_num(g("id"))),
        name=g("name"),
        position=g("position"),
        team_name=g("team_name"),
        price=int(_num(g("price"))),
        price_increment=int(_num(g("price_increment"))),
        status=status,
        status_label=STATUS_LABEL.get(status or "", status or "—"),
        will_play=will_play,
        expected_ppg=expected,
        basis=basis,
        status_info=status_info,
        news_title=news,
        note=note,
        sell_now=sell_now,
        reason=reason.strip(" ·"),
    )
