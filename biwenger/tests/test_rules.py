"""Tests de las constantes de la normativa (Pain&Gain 26/27)."""

from __future__ import annotations

from biwenger.rules import LEAGUE_RULES


def test_real_money_penalties_by_position():
    rm = LEAGUE_RULES.real_money
    assert rm.penalty_for_rank_from_bottom(1) == 3.0   # último
    assert rm.penalty_for_rank_from_bottom(2) == 2.0   # penúltimo
    assert rm.penalty_for_rank_from_bottom(3) == 1.0   # antepenúltimo
    assert rm.penalty_for_rank_from_bottom(4) == 0.0   # el resto no paga
    assert rm.deposit_eur == 30.0


def test_ingame_prizes():
    p = LEAGUE_RULES.prizes
    assert (p.first, p.second, p.third) == (1_000_000, 500_000, 250_000)
    assert p.ideal_eleven_per_player == 500_000
    assert p.mvp == 750_000


def test_loan_bounds():
    loans = LEAGUE_RULES.loans
    assert loans.min_amount == 200_000
    assert loans.max_amount == 1_000_000
    assert loans.max_loans_per_round == 3
    assert loans.max_received_per_player_round == 2
