"""Tests del normalizador de respuestas de la API (offline)."""

from __future__ import annotations

from biwenger.api.parse import extract_players, player_points, unwrap


def test_unwrap_removes_data_envelope(competition_data):
    body = unwrap(competition_data)
    assert "players" in body
    assert "data" not in body  # ya desenvuelto


def test_extract_players_from_dict_shape(competition_data):
    players = extract_players(competition_data)
    assert len(players) == 4
    names = {p["name"] for p in players}
    assert {"Lewandowski", "Vinicius", "Oblak"} <= names


def test_extract_players_from_list_shape():
    raw = {"data": {"players": [{"id": 1, "name": "X", "points": 10}]}}
    players = extract_players(raw)
    assert players[0]["name"] == "X"


def test_extract_players_empty_when_missing():
    assert extract_players({"data": {}}) == []
    assert extract_players({}) == []


def test_player_points_reads_points(competition_data):
    players = {p["name"]: p for p in extract_players(competition_data)}
    assert player_points(players["Lewandowski"]) == 210
    assert player_points({"totalPoints": 7}) == 7
    assert player_points({}) == 0
