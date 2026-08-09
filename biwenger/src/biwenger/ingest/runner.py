"""Orquestador de ingesta: junta cliente + parsers + persistencia.

Idempotente: se puede ejecutar a diario y solo añade lo nuevo. No hace red por
sí mismo; recibe un cliente (real o mock) para poder testearlo sin internet.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from biwenger.economy.engine import reconstruct
from biwenger.economy.pain import compute_pain_ledger, summarize_pain
from biwenger.db import models
from biwenger.ingest.board import parse_board
from biwenger.ingest.league import parse_standings
from biwenger.ingest.players import parse_competition_players
from biwenger.ingest.scout import scout_players
from biwenger.ingest.squads import parse_user_team
from biwenger.ingest import store
from biwenger.logging_setup import get_logger
from biwenger.rules import LEAGUE_RULES

log = get_logger(__name__)


def _detect_me(client: Any, settings: Any) -> tuple[int | None, int | None]:
    """Devuelve (mi_user_id_en_la_liga, mi_saldo_exacto) vía /account.

    Defensivo: si el cliente no soporta get_account o falla, cae a settings.user_id
    (sin saldo exacto).
    """
    fallback = int(settings.user_id) if str(settings.user_id).isdigit() else None
    if not hasattr(client, "get_account"):
        return fallback, None
    try:
        data = client.get_account()
        data = data.get("data", data) if isinstance(data, dict) else {}
        for lg in data.get("leagues", []) or []:
            if not isinstance(lg, dict) or str(lg.get("id")) != str(settings.league_id):
                continue
            user = lg.get("user") if isinstance(lg.get("user"), dict) else {}
            uid = user.get("id")
            uid = int(uid) if isinstance(uid, (int, str)) and str(uid).isdigit() else fallback
            balance = user.get("balance") if isinstance(user.get("balance"), int) else None
            return uid, balance
    except Exception as exc:  # noqa: BLE001 - degradamos con seguridad
        log.warning("No se pudo leer /account para detectar mi saldo: %s", exc)
    return fallback, None


def _ingest_squads(client: Any, session: Session, standings: list[dict], today: date) -> dict[int, int]:
    """Ingiere las plantillas ACTUALES de todos los managers y devuelve el coste
    de la plantilla INICIAL de cada uno (capturado una sola vez).

    - Guarda una foto de la plantilla del día (para 'biwenger squads').
    - La primera vez, fija User.initial_squad_cost = Σ owner.price (saldo de
      partida = 40M − ese coste). Luego no lo recalcula.
    """
    costs: dict[int, int] = {}
    can_fetch = hasattr(client, "get_user_team")
    for s in standings:
        uid = s["user_id"]
        user = session.get(models.User, uid)
        if user is None:
            continue
        if can_fetch:
            try:
                team = parse_user_team(client.get_user_team(str(uid)))
                squad = team["squad"]
                store.store_squad(session, today, uid, squad)
                if user.initial_squad_cost is None:
                    user.initial_squad_cost = sum((p.get("buy_price") or 0) for p in squad)
            except Exception as exc:  # noqa: BLE001 - degradamos con seguridad
                log.warning("No se pudo leer la plantilla de %s: %s", uid, exc)
        if user.initial_squad_cost is not None:
            costs[uid] = user.initial_squad_cost
    session.flush()
    return costs


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

    # 2b) Mi id de usuario EN LA LIGA y mi saldo exacto (la API expone el mío).
    #     El X-User configurado puede ser el id de cuenta; el de standings es el
    #     de membresía en la liga. Los resolvemos vía /account de forma defensiva.
    my_league_uid, my_balance = _detect_me(client, settings)
    exact_cash = {my_league_uid: my_balance} if (my_league_uid and my_balance is not None) else {}

    users = [
        {
            "id": s["user_id"],
            "name": s["name"],
            "is_me": my_league_uid is not None and s["user_id"] == my_league_uid,
        }
        for s in standings
    ]

    # 3) Persistir maestros y movimientos.
    store.upsert_users(session, users)
    n_new = store.store_movements(session, parsed.movements)
    store.store_round_standings(session, parsed.round_results)

    # 3b) Guardar la plantilla actual de cada manager (para las pestañas de
    #     equipos). No se usa para la economía: el saldo se estima como
    #     40M − valor_de_equipo (+ primas + cesiones), ver economy/engine.py.
    _ingest_squads(client, session, standings, today)

    # 4) Motor económico (saldo = 40M − valor equipo + primas; mi saldo, exacto).
    economies = reconstruct(
        parsed.movements,
        parsed.round_results,
        team_values,
        initial_budget=settings.initial_budget,
        factor=settings.bid_team_value_factor,
        user_names=user_names,
        exact_cash=exact_cash,
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

    # 7) Scouting de MI plantilla: estado físico, noticias, forma, minutos.
    scouted = 0
    if my_league_uid is not None and hasattr(client, "get_player_detail"):
        my_player_ids = list(session.scalars(
            select(models.UserSquad.player_id).where(
                models.UserSquad.date == today,
                models.UserSquad.user_id == my_league_uid,
            )
        ))
        if my_player_ids:
            scouted = scout_players(
                client, session, my_player_ids,
                score_name=settings.score_default, today=today,
            )

    return {
        "date": today,
        "movements_total": len(parsed.movements),
        "movements_new": n_new,
        "round_results": len(parsed.round_results),
        "managers": len(economies),
        "players_new": players_new,
        "scouted": scouted,
        "unknown_types": dict(parsed.unknown_types),
        "economy": economies,
        "pain": summarize_pain(pain_entries),
    }
