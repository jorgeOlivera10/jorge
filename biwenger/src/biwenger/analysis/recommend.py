"""Recomendaciones: detección de chollos y sugerencia de puja.

- Chollos: jugadores infravalorados = mucho 'expected_points' por poco precio
  (value_ratio alto), con partidos suficientes para no ser un espejismo y sin
  lesión. Se puede filtrar por posición y precio máximo.
- Sugerencia de puja: cruza el precio de mercado con TU puja máxima y con el
  techo de puja de tus rivales (que el motor económico ya estima), para decirte
  cuánto ofrecer y si puedes quedártelo.
"""

from __future__ import annotations

from dataclasses import dataclass

from biwenger.analysis.expected import PlayerValue


def _fmt(n: int | float) -> str:
    return f"€{n:,.0f}"


def rank_chollos(
    values: list[PlayerValue],
    *,
    min_games: int = 3,
    max_price: int | None = None,
    position: int | None = None,
    top: int = 20,
) -> list[PlayerValue]:
    """Devuelve los mejores chollos ordenados por value_ratio descendente."""
    candidates = [
        v
        for v in values
        if v.played >= min_games
        and v.value_ratio > 0
        and (max_price is None or v.price <= max_price)
        and (position is None or v.position == position)
        and (v.status in (None, "ok", "playing"))
    ]
    candidates.sort(key=lambda v: v.value_ratio, reverse=True)
    return candidates[:top]


@dataclass
class RivalCeiling:
    user_id: int
    name: str | None
    max_bid: int


@dataclass
class BidSuggestion:
    player_id: int
    player_name: str | None
    market_price: int
    my_max_bid: int
    value_bid: int              # precio de mercado + margen (puja "de valor")
    bid_to_beat_rivals: int     # justo por encima del techo del mayor rival
    suggested_bid: int          # recomendación final (acotada por tu puja máxima)
    top_rival: RivalCeiling | None
    can_afford: bool            # tu puja máxima cubre la sugerencia
    can_outbid_everyone: bool   # tu puja máxima supera a todos los rivales
    note: str


def suggest_bid(
    target: PlayerValue,
    my_max_bid: int,
    rival_ceilings: list[RivalCeiling],
    *,
    margin: float = 0.15,
) -> BidSuggestion:
    """Sugiere cuánto pujar por `target` teniendo en cuenta a los rivales."""
    market = target.price
    value_bid = int(round(market * (1 + margin)))

    rivals = sorted(rival_ceilings, key=lambda r: r.max_bid, reverse=True)
    top_rival = rivals[0] if rivals else None
    top_ceiling = top_rival.max_bid if top_rival else 0

    # Informativo: cuánto tendrías que ofrecer para superar la CAPACIDAD del mayor
    # rival (su techo). No es la recomendación: un rival no gasta todo su banco en
    # un jugador cualquiera. Sirve para saber si, en una guerra, podrías ganarla.
    bid_to_beat = top_ceiling + 1 if top_ceiling >= market else value_bid
    can_outbid_everyone = my_max_bid > top_ceiling

    # Recomendación: la puja de valor (mercado + margen), acotada por tu puja
    # máxima. La disposición real del rival es desconocida, así que no inflamos la
    # oferta hasta su capacidad: la mostramos aparte como aviso.
    suggested = min(value_bid, my_max_bid)
    can_afford = my_max_bid >= market

    if not can_afford:
        note = "No te llega ni al precio de mercado: no puedes ficharlo ahora."
    elif top_ceiling >= value_bid:
        note = (
            f"Ofrece ~{_fmt(suggested)}. Aviso: {top_rival.name if top_rival else 'un rival'} "
            f"tiene capacidad hasta {_fmt(top_ceiling)} si lo quisiera; "
            + ("podrías ganar una guerra de pujas." if can_outbid_everyone
               else f"por encima de tu techo ({_fmt(my_max_bid)}) no puedes competir.")
        )
    else:
        note = f"Ofrece ~{_fmt(suggested)}. Ningún rival tiene capacidad para superar esa puja."

    return BidSuggestion(
        player_id=target.player_id,
        player_name=target.name,
        market_price=market,
        my_max_bid=my_max_bid,
        value_bid=value_bid,
        bid_to_beat_rivals=bid_to_beat,
        suggested_bid=suggested,
        top_rival=top_rival,
        can_afford=can_afford,
        can_outbid_everyone=can_outbid_everyone,
        note=note,
    )
