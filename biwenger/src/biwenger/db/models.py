"""Modelos de datos (SQLAlchemy 2.0) para el histórico de la liga.

Diseñado para consultar el histórico: puntos por jornada y sistema, valores de
mercado diarios, plantillas por fecha, el feed completo del tablón y la economía
estimada de cada manager. Incluye también el ledger de dinero REAL (Pain tracker).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)  # id de Biwenger
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team_id: Mapped[int | None] = mapped_column(nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    position: Mapped[int | None] = mapped_column(nullable=True)  # 1 PT,2 DF,3 MC,4 DL
    price: Mapped[int | None] = mapped_column(nullable=True)     # valor de mercado actual
    price_increment: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ok, injured...
    # Agregados de rendimiento (de competition_data, 1 llamada para todos):
    total_points: Mapped[int | None] = mapped_column(nullable=True)
    played: Mapped[int | None] = mapped_column(nullable=True)
    points_home: Mapped[int | None] = mapped_column(nullable=True)
    played_home: Mapped[int | None] = mapped_column(nullable=True)
    points_away: Mapped[int | None] = mapped_column(nullable=True)
    played_away: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    points: Mapped[list["PlayerPoints"]] = relationship(back_populates="player")


class PlayerPoints(Base):
    """Puntos de un jugador en una jornada, para un sistema de puntuación."""

    __tablename__ = "player_points"
    __table_args__ = (
        UniqueConstraint("player_id", "round", "score_system", name="uq_points_player_round_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    round: Mapped[int] = mapped_column(Integer, index=True)          # jornada
    score_system: Mapped[str] = mapped_column(String(20))            # 'sofascore' | 'as'
    points: Mapped[int] = mapped_column(Integer, default=0)
    minutes: Mapped[int | None] = mapped_column(nullable=True)       # rawStats.minutesPlayed
    home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    match_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # finished...
    star: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    player: Mapped[Player] = relationship(back_populates="points")


class MarketValue(Base):
    """Valor de mercado de un jugador en una fecha (histórico de prices[])."""

    __tablename__ = "market_values"
    __table_args__ = (
        UniqueConstraint("player_id", "date", name="uq_marketvalue_player_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[int] = mapped_column(Integer)


class MarketDaily(Base):
    """Jugador puesto en el mercado un día concreto (con su precio y vendedor)."""

    __tablename__ = "market_daily"
    __table_args__ = (
        UniqueConstraint("date", "player_id", name="uq_marketdaily_date_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    price: Mapped[int | None] = mapped_column(nullable=True)
    seller_id: Mapped[int | None] = mapped_column(nullable=True)  # user id o None (banca)


class User(Base):
    """Manager de la liga (rival o yo mismo)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)  # id de usuario de Biwenger
    name: Mapped[str] = mapped_column(String(120))
    join_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_me: Mapped[bool] = mapped_column(Boolean, default=False)


class UserSquad(Base):
    """Foto de la plantilla de un manager en una fecha."""

    __tablename__ = "user_squads"
    __table_args__ = (
        UniqueConstraint("date", "user_id", "player_id", name="uq_squad_date_user_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    buy_price: Mapped[int | None] = mapped_column(nullable=True)  # owner.price (0/None = inicial)


class Movement(Base):
    """Un movimiento del tablón (fichaje, venta, prima, cesión, reto...).

    `dedup_key` es un hash natural del movimiento para que la ingesta sea
    IDEMPOTENTE (procesar solo movimientos nuevos), ya que el tablón no expone
    un id estable por línea.
    """

    __tablename__ = "movements"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_movement_dedup"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dedup_key: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)  # transfer, market, roundFinished...
    player_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    amount: Mapped[int | None] = mapped_column(nullable=True)
    from_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    to_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    round: Mapped[int | None] = mapped_column(nullable=True)
    # Para movimientos que no encajan (cesiones/retos aún por confirmar): guardamos
    # una nota para poder revisarlos ("detectar y avisar").
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)


class UserEconomy(Base):
    """Snapshot diario de la economía estimada de un manager."""

    __tablename__ = "user_economy"
    __table_args__ = (
        UniqueConstraint("date", "user_id", name="uq_economy_date_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    cash: Mapped[int] = mapped_column(Integer)         # saldo estimado
    team_value: Mapped[int] = mapped_column(Integer)   # valor de plantilla
    max_bid: Mapped[int] = mapped_column(Integer)      # puja máxima = cash + factor*team_value


class RoundStanding(Base):
    """Clasificación de un manager en una jornada (de rounds/league)."""

    __tablename__ = "round_standings"
    __table_args__ = (
        UniqueConstraint("round", "user_id", name="uq_round_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    round: Mapped[int] = mapped_column(Integer, index=True)
    round_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    position: Mapped[int | None] = mapped_column(nullable=True)   # posición en la jornada
    points: Mapped[int | None] = mapped_column(nullable=True)
    bonus: Mapped[int | None] = mapped_column(nullable=True)      # prima in-game


class RealMoneyLedger(Base):
    """Ledger de dinero REAL (Pain tracker): castigos por jornada, fianza, etc."""

    __tablename__ = "real_money_ledger"
    __table_args__ = (
        UniqueConstraint("round", "user_id", "concept", name="uq_ledger_round_user_concept"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    round: Mapped[int | None] = mapped_column(nullable=True, index=True)  # None = fianza/entrada
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    concept: Mapped[str] = mapped_column(String(40))   # 'entry', 'deposit', 'penalty', 'deposit_reset'
    amount_eur: Mapped[float] = mapped_column(Float)   # negativo = coste para el manager
