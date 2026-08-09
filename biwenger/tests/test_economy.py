"""Tests del motor económico (modelo saldo = 40M − valor equipo + primas)."""

from __future__ import annotations

from biwenger.economy.engine import reconstruct
from biwenger.ingest.board import parse_board
from tests.conftest import load_fixture

TV = {501: 30_000_000, 502: 25_000_000, 503: 10_000_000}


def parsed():
    return parse_board(load_fixture("board_sample.json"))


def econ(team_values=None, **kw):
    res = parsed()
    return reconstruct(res.movements, res.round_results, team_values or TV,
                       initial_budget=40_000_000, factor=0.25, **kw)


def test_cash_is_budget_minus_team_value_plus_awards():
    # Jorge (501): 40M − 30M valor + 1M prima (roundFinished) = 11M
    jorge = next(e for e in econ() if e.user_id == 501)
    assert jorge.awards == 1_000_000
    assert jorge.cash == 11_000_000


def test_max_bid_formula():
    jorge = next(e for e in econ() if e.user_id == 501)
    # 11M + 0.25 * 30M = 18.5M
    assert jorge.max_bid == 18_500_000


def test_special_flows_from_loans_affect_cash():
    # Rival B (503): 40M − 10M + 0 primas + 0.3M (cesión cobrada) = 30.3M
    rival_b = next(e for e in econ() if e.user_id == 503)
    assert rival_b.cash == 30_300_000
    # Rival A (502): 40M − 25M + 0.5M prima − 0.3M (cesión pagada) = 15.2M
    rival_a = next(e for e in econ() if e.user_id == 502)
    assert rival_a.cash == 15_200_000
    assert any("cesiones" in f for f in rival_a.flags)


def test_exact_cash_overrides_estimate():
    me = next(e for e in econ(exact_cash={501: 13_420_000}) if e.user_id == 501)
    assert me.is_exact is True
    assert me.cash == 13_420_000
    assert me.max_bid == 13_420_000 + 7_500_000
    assert any("EXACTO" in f for f in me.flags)


def test_excluding_unknown_types_changes_cash():
    with_loans = next(e for e in econ() if e.user_id == 502)
    without = next(e for e in econ(include_unknown_types=False) if e.user_id == 502)
    # Sin la cesión de 300k que paga 502, su saldo es 300k mayor.
    assert without.cash == with_loans.cash + 300_000
