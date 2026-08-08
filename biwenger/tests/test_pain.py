"""Tests del Pain tracker (dinero real)."""

from __future__ import annotations

from biwenger.economy.pain import compute_pain_ledger, summarize_pain
from biwenger.ingest.board import ParsedRoundResult
from biwenger.rules import LEAGUE_RULES


def _r(rnd, uid, position, points):
    return ParsedRoundResult(round=rnd, round_name=f"J{rnd}", user_id=uid,
                             user_name=f"U{uid}", position=position, points=points, bonus=None)


def test_penalties_by_position_in_round():
    # 4 managers en la jornada 1: posiciones 1..4 (4 = último)
    results = [_r(1, 1, 1, 90), _r(1, 2, 2, 80), _r(1, 3, 3, 70), _r(1, 4, 4, 60)]
    entries = compute_pain_ledger(results, LEAGUE_RULES)
    by_user = {e.user_id: e.amount_eur for e in entries if e.concept == "penalty"}
    assert by_user[4] == 3.0   # último
    assert by_user[3] == 2.0   # penúltimo
    assert by_user[2] == 1.0   # antepenúltimo
    assert 1 not in by_user    # el primero no paga


def test_ranking_uses_points_when_position_missing():
    results = [
        ParsedRoundResult(1, "J1", 1, "U1", None, 30, None),
        ParsedRoundResult(1, "J1", 2, "U2", None, 10, None),  # menos puntos -> último
        ParsedRoundResult(1, "J1", 3, "U3", None, 20, None),
    ]
    entries = compute_pain_ledger(results, LEAGUE_RULES)
    pen = {e.user_id: e.amount_eur for e in entries if e.concept == "penalty"}
    assert pen[2] == 3.0   # último por menos puntos
    assert pen[3] == 2.0
    assert pen[1] == 1.0


def test_deposit_reset_triggers_at_threshold():
    # Un manager que queda último (3€) durante 10 jornadas -> 30€ -> re-fianza.
    results = []
    for rnd in range(1, 11):
        results += [_r(rnd, 1, 2, 80), _r(rnd, 9, 1, 90), _r(rnd, 2, 3, 10)]  # uid 2 siempre último
    entries = compute_pain_ledger(results, LEAGUE_RULES)
    resets = [e for e in entries if e.concept == "deposit_reset" and e.user_id == 2]
    assert len(resets) == 1
    assert resets[0].amount_eur == 30.0


def test_summarize_totals():
    results = [_r(1, 1, 1, 90), _r(1, 2, 2, 80), _r(1, 3, 3, 70)]
    totals = summarize_pain(compute_pain_ledger(results, LEAGUE_RULES))
    by_user = {t.user_id: t for t in totals}
    assert by_user[3].total_eur == 3.0   # último
    assert by_user[2].total_eur == 2.0
