"""Tests del parser del mercado (offline, defensivo)."""

from __future__ import annotations

from biwenger.ingest.market import parse_market


def test_parse_market_sales_with_player_dict_and_seller():
    raw = {
        "data": {
            "sales": [
                {"price": 5_000_000, "until": 1723300000,
                 "user": {"id": 502, "name": "Rival A"}, "player": {"id": 1002}},
                {"price": 3_000_000, "player": 1003},  # de la banca (sin user), player como int
            ],
            "offers": [],
        }
    }
    out = parse_market(raw)
    assert len(out) == 2
    assert out[0]["player_id"] == 1002
    assert out[0]["price"] == 5_000_000
    assert out[0]["seller_id"] == 502
    assert out[1]["player_id"] == 1003
    assert out[1]["seller_id"] is None      # banca


def test_parse_market_alternate_key_and_userID():
    raw = {"data": {"market": [{"price": 100, "player": 7, "userID": 999}]}}
    out = parse_market(raw)
    assert out[0]["player_id"] == 7
    assert out[0]["seller_id"] == 999


def test_parse_market_empty_or_unknown_shape():
    assert parse_market({"data": {}}) == []
    assert parse_market({}) == []
    assert parse_market({"data": {"sales": [{"no_player": 1}]}}) == []
