"""Persistencia idempotente en BD de lo que producen los parsers.

'Idempotente' = ejecutar dos veces no duplica filas. Se apoya en las
UniqueConstraint del modelo y en el dedup_key de los movimientos del tablón.
Devuelve el nº de filas NUEVAS para poder informar "solo lo nuevo".
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from biwenger.db import models
from biwenger.ingest.board import ParsedMovement, ParsedRoundResult


def upsert_players(session: Session, players: Iterable[dict[str, Any]]) -> int:
    n = 0
    for p in players:
        obj = session.get(models.Player, p["id"])
        if obj is None:
            session.add(models.Player(**p))
            n += 1
        else:
            for k, v in p.items():
                if k != "id":
                    setattr(obj, k, v)
    session.flush()
    return n


def upsert_users(session: Session, users: Iterable[dict[str, Any]]) -> int:
    n = 0
    for u in users:
        if u.get("id") is None:
            continue
        obj = session.get(models.User, u["id"])
        if obj is None:
            session.add(
                models.User(
                    id=u["id"],
                    name=u.get("name") or str(u["id"]),
                    join_date=u.get("join_date"),
                    is_me=bool(u.get("is_me", False)),
                )
            )
            n += 1
        else:
            if u.get("name"):
                obj.name = u["name"]
            if u.get("join_date"):
                obj.join_date = u["join_date"]
            if u.get("is_me"):
                obj.is_me = True
    session.flush()
    return n


def store_movements(session: Session, movements: Iterable[ParsedMovement]) -> int:
    """Inserta solo los movimientos cuyo dedup_key no exista ya."""
    movements = list(movements)
    if not movements:
        return 0
    keys = {m.dedup_key for m in movements}
    existing = set(
        session.scalars(
            select(models.Movement.dedup_key).where(models.Movement.dedup_key.in_(keys))
        )
    )
    n = 0
    for m in movements:
        if m.dedup_key in existing:
            continue
        session.add(
            models.Movement(
                dedup_key=m.dedup_key,
                date=m.date,
                type=m.type,
                player_id=m.player_id,
                amount=m.amount,
                from_user_id=m.from_user_id,
                to_user_id=m.to_user_id,
                note=m.note,
            )
        )
        existing.add(m.dedup_key)  # evita duplicados dentro del mismo lote
        n += 1
    session.flush()
    return n


def store_round_standings(session: Session, results: Iterable[ParsedRoundResult]) -> int:
    n = 0
    for r in results:
        if r.round is None:
            continue
        obj = session.scalar(
            select(models.RoundStanding).where(
                models.RoundStanding.round == r.round,
                models.RoundStanding.user_id == r.user_id,
            )
        )
        if obj is None:
            session.add(
                models.RoundStanding(
                    round=r.round,
                    round_name=r.round_name,
                    user_id=r.user_id,
                    position=r.position,
                    points=r.points,
                    bonus=r.bonus,
                )
            )
            n += 1
        else:
            obj.position, obj.points, obj.bonus = r.position, r.points, r.bonus
    session.flush()
    return n


def store_market_values(session: Session, values: Iterable[dict[str, Any]]) -> int:
    values = list(values)
    if not values:
        return 0
    n = 0
    for v in values:
        exists = session.scalar(
            select(models.MarketValue.id).where(
                models.MarketValue.player_id == v["player_id"],
                models.MarketValue.date == v["date"],
            )
        )
        if exists is None:
            session.add(models.MarketValue(**v))
            n += 1
    session.flush()
    return n


def store_player_points(session: Session, points: Iterable[dict[str, Any]]) -> int:
    n = 0
    for pt in points:
        obj = session.scalar(
            select(models.PlayerPoints).where(
                models.PlayerPoints.player_id == pt["player_id"],
                models.PlayerPoints.round == pt["round"],
                models.PlayerPoints.score_system == pt["score_system"],
            )
        )
        if obj is None:
            session.add(models.PlayerPoints(**pt))
            n += 1
        else:
            for k, v in pt.items():
                setattr(obj, k, v)
    session.flush()
    return n


def store_user_economy(
    session: Session, snapshot_date: date, economies: Iterable[Any]
) -> int:
    """Guarda el snapshot diario de economía (idempotente por fecha+usuario)."""
    n = 0
    for e in economies:
        obj = session.scalar(
            select(models.UserEconomy).where(
                models.UserEconomy.date == snapshot_date,
                models.UserEconomy.user_id == e.user_id,
            )
        )
        if obj is None:
            session.add(
                models.UserEconomy(
                    date=snapshot_date,
                    user_id=e.user_id,
                    cash=e.cash,
                    team_value=e.team_value,
                    max_bid=e.max_bid,
                )
            )
            n += 1
        else:
            obj.cash, obj.team_value, obj.max_bid = e.cash, e.team_value, e.max_bid
    session.flush()
    return n


def store_real_money_ledger(session: Session, entries: Iterable[Any]) -> int:
    """Guarda las entradas del Pain tracker (idempotente por round+user+concept)."""
    n = 0
    for e in entries:
        obj = session.scalar(
            select(models.RealMoneyLedger).where(
                models.RealMoneyLedger.round == e.round,
                models.RealMoneyLedger.user_id == e.user_id,
                models.RealMoneyLedger.concept == e.concept,
            )
        )
        if obj is None:
            session.add(
                models.RealMoneyLedger(
                    round=e.round,
                    user_id=e.user_id,
                    concept=e.concept,
                    amount_eur=e.amount_eur,
                )
            )
            n += 1
        else:
            obj.amount_eur = e.amount_eur
    session.flush()
    return n


def store_market_daily(session: Session, snapshot_date: date, sales: Iterable[dict[str, Any]]) -> int:
    """Guarda los jugadores en el mercado de un día (idempotente por fecha+jugador)."""
    n = 0
    for sale in sales:
        pid = sale.get("player_id")
        if pid is None:
            continue
        exists = session.scalar(
            select(models.MarketDaily.id).where(
                models.MarketDaily.date == snapshot_date,
                models.MarketDaily.player_id == pid,
            )
        )
        if exists is None:
            session.add(models.MarketDaily(
                date=snapshot_date, player_id=pid,
                price=sale.get("price"), seller_id=sale.get("seller_id"),
            ))
            n += 1
    session.flush()
    return n


def update_player_scouting(session: Session, detail: dict[str, Any]) -> None:
    """Actualiza los campos de scouting de un Player desde una ficha parseada."""
    from datetime import datetime

    pid = detail.get("player_id")
    if pid is None:
        return
    player = session.get(models.Player, pid)
    if player is None:
        return
    if detail.get("status"):
        player.status = detail["status"]
    player.status_info = detail.get("status_info")
    player.news_title = detail.get("news_title")
    player.news_date = detail.get("news_date")
    player.fitness_avg = detail.get("fitness_avg")
    player.last_season_points = detail.get("last_season_points")
    player.last_season_games = detail.get("last_season_games")
    player.scouted_at = datetime.utcnow()
    session.flush()


def store_player_news(session: Session, player_id: int, news: Iterable[dict[str, Any]]) -> int:
    n = 0
    for item in news:
        if not item.get("date") or not item.get("title"):
            continue
        exists = session.scalar(
            select(models.PlayerNews.id).where(
                models.PlayerNews.player_id == player_id,
                models.PlayerNews.date == item["date"],
                models.PlayerNews.title == item["title"],
            )
        )
        if exists is None:
            session.add(models.PlayerNews(
                player_id=player_id, date=item["date"],
                title=item["title"], content=item.get("content"),
            ))
            n += 1
    session.flush()
    return n


def store_squad(session: Session, snapshot_date: date, user_id: int, squad: Iterable[dict[str, Any]]) -> int:
    n = 0
    for row in squad:
        exists = session.scalar(
            select(models.UserSquad.id).where(
                models.UserSquad.date == snapshot_date,
                models.UserSquad.user_id == user_id,
                models.UserSquad.player_id == row["player_id"],
            )
        )
        if exists is None:
            session.add(
                models.UserSquad(
                    date=snapshot_date,
                    user_id=user_id,
                    player_id=row["player_id"],
                    buy_price=row.get("buy_price"),
                )
            )
            n += 1
    session.flush()
    return n
