"""Orquestador de ingesta: junta cliente + parsers + persistencia.

Idempotente: se puede ejecutar a diario y solo añade lo nuevo. No hace red por
sí mismo; recibe un cliente (real o mock) para poder testearlo sin internet.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from biwenger.economy.engine import reconstruct
from biwenger.economy.pain import compute_pain_ledger, summarize_pain
from biwenger.ingest.board import parse_board
from biwenger.ingest.league import parse_standings
from biwenger.ingest.players import parse_competition_players
from biwenger.ingest import store
from biwenger.logging_setup import get_logger
from biwenger.rules import LEAGUE_RULES

log = get_logger(__name__)


def run_ingest(client: Any, settings: Any, session: Session, *, today: date | None = None) -> dict[str, Any]:
    """Ejecuta una pasada de ingesta completa (tablón + liga + economía + pain)."""
    today = today or date.today()

    # 1) Tablón completo (idempotente vía dedup_key).
    board = client.get_full_board()
    parsed = parse_board(board)
    log.info("Tablón: %d movimientos, %d resultados de jornada",
             len(parsed.movements), len(parsed.round_results))
    if parsed.unknown_types:
        log.warning("Tipos de movimiento no reconocidos (revisar): %s", parsed.unknown_types)

    # 2) Standings de la liga (valor de equipo + nombres).
    standings = parse_standings(client.get_league())
    team_values = {s["user_id"]: s["team_value"] for s in standings}
    user_names = {s["user_id"]: s["name"] for s in standings}
    users = [
        {"id": s["user_id"], "name": s["name"], "is_me": str(s["user_id"]) == str(settings.user_id)}
        for s in standings
    ]

    # 3) Persistir maestros y movimientos.
    store.upsert_users(session, users)
    n_new = store.store_movements(session, parsed.movements)
    store.store_round_standings(session, parsed.round_results)

    # 4) Motor económico.
    economies = reconstruct(
        parsed.movements,
        parsed.round_results,
        team_values,
        initial_budget=settings.initial_budget,
        factor=settings.bid_team_value_factor,
        user_names=user_names,
    )
    store.store_user_economy(session, today, economies)

    # 5) Pain tracker (dinero real).
    pain_entries = compute_pain_ledger(parsed.round_results, LEAGUE_RULES)
    store.store_real_money_ledger(session, pain_entries)

    # 6) Jugadores + valor de mercado del día (1 sola llamada al 'data' de
    #    competición). Defensivo: si el cliente no lo soporta o falla, se omite.
    players_new = 0
    if hasattr(client, "get_competition_data"):
        try:
            raw_players = client.get_competition_data(settings.score_default)
            players = parse_competition_players(raw_players)
            players_new = store.upsert_players(session, players)
            market_values = [
                {"player_id": p["id"], "date": today, "price": p["price"]}
                for p in players
                if p.get("price") is not None
            ]
            store.store_market_values(session, market_values)
            log.info("Jugadores ingeridos: %d (nuevos %d)", len(players), players_new)
        except Exception as exc:  # noqa: BLE001 - la API es no oficial; degradamos
            log.warning("No se pudo ingerir jugadores: %s", exc)

    return {
        "date": today,
        "movements_total": len(parsed.movements),
        "movements_new": n_new,
        "round_results": len(parsed.round_results),
        "managers": len(economies),
        "players_new": players_new,
        "unknown_types": dict(parsed.unknown_types),
        "economy": economies,
        "pain": summarize_pain(pain_entries),
    }
