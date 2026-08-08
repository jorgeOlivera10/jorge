"""Tests del parser del tablón (offline, con fixture de ejemplo)."""

from __future__ import annotations

from biwenger.ingest.board import make_dedup_key, parse_board
from tests.conftest import load_fixture


def board():
    return load_fixture("board_sample.json")


def test_parses_transfers_and_market():
    res = parse_board(board())
    # 2 market + 1 transfer + 1 loan(desconocido) = 4 movimientos
    assert len(res.movements) == 4
    market = [m for m in res.movements if m.type == "market"]
    assert len(market) == 2
    assert {m.player_id for m in market} == {1001, 1002}
    # el market no tiene 'from' (viene de la banca)
    assert all(m.from_user_id is None for m in market)


def test_transfer_between_users_has_from_and_to():
    res = parse_board(board())
    transfer = next(m for m in res.movements if m.type == "transfer")
    assert transfer.from_user_id == 502
    assert transfer.to_user_id == 501
    assert transfer.player_id == 1003
    assert transfer.amount == 12000000


def test_round_finished_results_and_bonus():
    res = parse_board(board())
    assert len(res.round_results) == 3
    by_user = {r.user_id: r for r in res.round_results}
    assert by_user[501].round == 1
    assert by_user[501].position == 1
    assert by_user[501].bonus == 1000000
    assert by_user[502].bonus == 500000
    # el tercero no tiene bonus -> None
    assert by_user[503].bonus is None


def test_unknown_type_is_detected_and_flagged():
    res = parse_board(board())
    # 'loan' no es un tipo reconocido: se cuenta para avisar
    assert res.unknown_types == {"loan": 1}
    loan = next(m for m in res.movements if m.type == "loan")
    assert loan.note is not None
    assert loan.from_user_id == 503 and loan.to_user_id == 502
    assert loan.amount == 300000


def test_dedup_key_is_stable_and_idempotent():
    res1 = parse_board(board())
    res2 = parse_board(board())
    keys1 = sorted(m.dedup_key for m in res1.movements)
    keys2 = sorted(m.dedup_key for m in res2.movements)
    assert keys1 == keys2                      # estable entre ejecuciones
    assert len(set(keys1)) == len(keys1)       # sin colisiones en el fixture


def test_make_dedup_key_changes_with_inputs():
    a = make_dedup_key(1, "market", 1001, None, 501, 8000000)
    b = make_dedup_key(1, "market", 1001, None, 501, 9000000)
    assert a != b


def test_empty_board_is_safe():
    res = parse_board([])
    assert res.movements == [] and res.round_results == [] and res.unknown_types == {}
