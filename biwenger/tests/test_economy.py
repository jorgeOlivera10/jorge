"""Tests del motor económico (offline, sobre el fixture del tablón)."""

from __future__ import annotations

from biwenger.economy.engine import reconstruct
from biwenger.ingest.board import parse_board
from tests.conftest import load_fixture


def parsed():
    return parse_board(load_fixture("board_sample.json"))


def test_cash_reconstruction_matches_manual_calc():
    """Comprueba el saldo de Jorge (501) frente al cálculo a mano.

    Movimientos del fixture para 501:
      - market compra jugador 1001 por 8.0M  -> money_out += 8M
      - transfer: compra 1003 por 12M (to=501) -> money_out += 12M
      - roundFinished J1: bonus 1.0M          -> awards += 1M
    Presupuesto inicial 40M, sin coste de plantilla inicial:
      cash = 40M - 0 + 0(ventas) + 1M(prima) - 20M(fichajes) = 21M
    """
    res = parsed()
    econ = reconstruct(
        res.movements, res.round_results, team_values={501: 30_000_000, 502: 25_000_000, 503: 10_000_000},
        initial_budget=40_000_000, factor=0.25,
    )
    jorge = next(e for e in econ if e.user_id == 501)
    assert jorge.money_out == 20_000_000
    assert jorge.awards == 1_000_000
    assert jorge.cash == 21_000_000


def test_max_bid_formula():
    res = parsed()
    econ = reconstruct(
        res.movements, res.round_results, team_values={501: 30_000_000},
        initial_budget=40_000_000, factor=0.25,
    )
    jorge = next(e for e in econ if e.user_id == 501)
    # max_bid = cash + 0.25 * team_value = 21M + 7.5M = 28.5M
    assert jorge.max_bid == 28_500_000


def test_rival_a_receives_sale_and_award():
    """Rival A (502): compra 1002 por 5M, vende 1003 por 12M, prima 500k, recibe cesión 300k."""
    res = parsed()
    econ = reconstruct(
        res.movements, res.round_results, team_values={502: 25_000_000},
        initial_budget=40_000_000, factor=0.25, include_unknown_types=True,
    )
    rival = next(e for e in econ if e.user_id == 502)
    # 502 compra 1002 (5M) y paga la cesión 'loan' de 300k (502 es 'to') -> money_out = 5.3M
    assert rival.money_out == 5_300_000
    # 502 vende 1003 (from) -> money_in = 12M
    assert rival.money_in == 12_000_000
    assert rival.awards == 500_000
    # cash = 40M + 12M + 0.5M - (5M compra + 0.3M cesión) = 47.2M
    assert rival.cash == 47_200_000
    assert any("cesiones" in f for f in rival.flags)


def test_excluding_unknown_types_changes_cash():
    res = parsed()
    with_loans = reconstruct(res.movements, res.round_results, {502: 0},
                             initial_budget=40_000_000, include_unknown_types=True)
    without = reconstruct(res.movements, res.round_results, {502: 0},
                          initial_budget=40_000_000, include_unknown_types=False)
    r_with = next(e for e in with_loans if e.user_id == 502)
    r_without = next(e for e in without if e.user_id == 502)
    # Sin la cesión de 300k, 502 no paga esos 300k -> más saldo.
    assert r_without.cash == r_with.cash + 300_000
