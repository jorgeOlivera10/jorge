"""Scouting: enriquece un conjunto de jugadores con su ficha detallada.

Hace UNA petición por jugador (la ficha trae estado, noticias, forma, puntos por
jornada y precios), así que se usa sobre conjuntos ACOTADOS: tu plantilla y los
jugadores de la banca en el mercado (los que te interesan). Respeta el throttling
del cliente.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from sqlalchemy.orm import Session

from biwenger.db import models
from biwenger.ingest.detail import parse_player_detail
from biwenger.ingest.players import parse_player_prices, parse_player_reports
from biwenger.ingest import store
from biwenger.logging_setup import get_logger

log = get_logger(__name__)


def scout_players(
    client: Any,
    session: Session,
    player_ids: Iterable[int],
    *,
    score_name: str,
    today: date | None = None,
) -> int:
    """Descarga y guarda la ficha de cada jugador dado. Devuelve nº scouteados."""
    today = today or date.today()
    n = 0
    for pid in dict.fromkeys(player_ids):  # únicos, preservando orden
        player = session.get(models.Player, pid)
        alias = (player.slug if player else None) or str(pid)
        try:
            raw = client.get_player_detail(alias, score_name)
        except Exception as exc:  # noqa: BLE001 - degradamos por jugador
            log.warning("No se pudo scoutear al jugador %s: %s", pid, exc)
            continue

        detail = parse_player_detail(raw)
        store.update_player_scouting(session, detail)
        # Guardamos las noticias bajo el id del jugador que DEVUELVE la ficha
        # (consistente con el resto), no bajo el id pedido.
        store.store_player_news(session, detail.get("player_id") or pid, detail.get("news", []))
        # Puntos por jornada (con minutos) y precios históricos.
        store.store_player_points(session, parse_player_reports(raw, score_name))
        store.store_market_values(session, parse_player_prices(raw))
        n += 1
    return n
