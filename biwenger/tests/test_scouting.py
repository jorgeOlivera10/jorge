"""Tests del parseo de la ficha detallada y del veredicto por jugador."""

from __future__ import annotations

from types import SimpleNamespace

from biwenger.analysis.scouting import player_outlook
from biwenger.ingest.detail import parse_player_detail
from tests.conftest import load_fixture


def test_parse_player_detail_status_and_news():
    d = parse_player_detail(load_fixture("player_detail_sample.json"))
    assert d["player_id"] == 1001
    assert d["status"] == "doubt"
    assert d["is_risky"] is True
    # La noticia genérica del blog se filtra; solo quedan las que mencionan al
    # jugador. La más reciente primero.
    assert d["news_title"] == "Lewandowski, duda por unas molestias"
    assert len(d["news"]) == 2
    assert all("lewandowski" in n["title"].lower() for n in d["news"])
    assert d["last_season_points"] == 220 and d["last_season_games"] == 36
    assert d["fitness_avg"] == round((8 + 6 + 10 + 7) / 4, 2)


def _player(**kw):
    base = dict(id=1, name="X", position=4, team_name="T", price=5_000_000,
                price_increment=0, status="ok", played=0, total_points=0,
                last_season_points=None, last_season_games=None,
                status_info=None, news_title=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_outlook_uses_last_season_when_no_current_points():
    p = _player(status="ok", played=0, last_season_points=200, last_season_games=38)
    o = player_outlook(p)
    assert o.basis == "temp. pasada"
    assert o.expected_ppg == round(200 / 38, 2)
    assert o.will_play == "Titular"        # 38 partidos la temporada pasada
    assert o.sell_now is False


def test_outlook_injured_triggers_sell():
    p = _player(status="injured", last_season_games=30, last_season_points=150)
    o = player_outlook(p)
    assert o.sell_now is True
    assert o.will_play == "No disponible"
    assert "LESIONADO" in o.status_label


def test_outlook_sell_on_injury_status_info():
    # El motivo del estado (statusInfo) es específico del jugador: si menciona
    # lesión/baja, se marca venta aunque el status no sea de riesgo.
    p = _player(status="ok", status_info="Rotura de fibras, baja 3 semanas",
                last_season_games=25, last_season_points=120)
    o = player_outlook(p)
    assert o.sell_now is True
    assert o.note == "Rotura de fibras, baja 3 semanas"


def test_outlook_ignores_generic_news_for_sell():
    # Una noticia genérica del blog NO debe disparar venta (no es del jugador).
    p = _player(status="ok", news_title="Jugadores a elegir como Ariete: Jornada 3",
                last_season_games=30, last_season_points=180)
    o = player_outlook(p)
    assert o.sell_now is False


def test_outlook_low_games_is_not_starter():
    p = _player(status="ok", played=0, last_season_points=20, last_season_games=6)
    o = player_outlook(p)
    assert o.will_play == "Poco habitual"
