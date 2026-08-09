"""Tests del análisis: puntos esperados, chollos y sugerencia de puja (offline)."""

from __future__ import annotations

from biwenger.analysis.expected import analyze_players, compute_player_value
from biwenger.analysis.recommend import RivalCeiling, rank_chollos, suggest_bid


def _p(pid, name, price, total_points, played, position=3, inc=0, status="ok", team="X"):
    return {
        "id": pid, "name": name, "price": price, "total_points": total_points,
        "played": played, "position": position, "price_increment": inc,
        "status": status, "team_name": team,
    }


def test_points_per_match_and_value_ratio():
    v = compute_player_value(_p(1, "Barato", 2_000_000, 60, 10), rounds_played=10)
    assert v.points_per_match == 6.0            # 60 / 10
    assert v.reliability == 1.0                 # jugó todas
    # expected = 6 * 1 * (1+0) = 6 ; value = 6 / 2 = 3.0 pts por millón
    assert v.expected_points == 6.0
    assert v.value_ratio == 3.0


def test_reliability_penalizes_low_minutes():
    # Juega solo 3 de 10 jornadas -> reliability 0.3
    v = compute_player_value(_p(2, "Suplente", 1_000_000, 30, 3), rounds_played=10)
    assert v.reliability == 0.3
    assert v.expected_points == round(10.0 * 0.3, 2)   # ppm 10 * 0.3


def test_momentum_from_price_increment():
    v = compute_player_value(
        _p(3, "EnAlza", 5_000_000, 50, 10, inc=500_000), rounds_played=10
    )
    # momentum = 500k/5M = 0.1 -> expected = 5 * 1 * 1.1 = 5.5
    assert v.momentum == 0.1
    assert v.expected_points == 5.5


def test_rank_chollos_orders_by_value_and_filters():
    players = [
        _p(1, "Chollo", 2_000_000, 60, 10),      # value 3.0
        _p(2, "Caro", 20_000_000, 60, 10),       # value 0.3
        _p(3, "PocosPartidos", 1_000_000, 20, 1),  # filtrado por min_games
        _p(4, "Lesionado", 2_000_000, 80, 10, status="injured"),  # filtrado por status
    ]
    values = analyze_players(players)
    chollos = rank_chollos(values, min_games=3, top=10)
    names = [c.name for c in chollos]
    assert names[0] == "Chollo"
    assert "PocosPartidos" not in names
    assert "Lesionado" not in names


def test_suggest_bid_when_i_can_outbid_everyone():
    values = analyze_players([_p(1, "Objetivo", 10_000_000, 80, 10)])
    target = values[0]
    rivals = [RivalCeiling(2, "Rival A", 8_000_000), RivalCeiling(3, "Rival B", 5_000_000)]
    sug = suggest_bid(target, my_max_bid=30_000_000, rival_ceilings=rivals)
    assert sug.can_outbid_everyone is True
    assert sug.value_bid == 11_500_000            # 10M + 15%
    assert sug.suggested_bid <= sug.my_max_bid


def test_suggest_bid_flags_stronger_rival():
    values = analyze_players([_p(1, "Objetivo", 10_000_000, 80, 10)])
    target = values[0]
    rivals = [RivalCeiling(2, "Ricachón", 25_000_000)]
    sug = suggest_bid(target, my_max_bid=12_000_000, rival_ceilings=rivals)
    assert sug.can_outbid_everyone is False
    assert "Ricachón" in sug.note
    # nunca sugiere por encima de mi puja máxima
    assert sug.suggested_bid <= 12_000_000
