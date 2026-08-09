"""Test del dashboard HTML autocontenido."""

from __future__ import annotations

from datetime import date

from biwenger.config import Settings
from biwenger.db.session import init_db, make_engine, session_scope
from biwenger.ingest.runner import run_ingest
from biwenger.webreport import build_dashboard_html, load_dashboard_data
from tests.conftest import load_fixture


class FakeClient:
    def get_full_board(self):
        return load_fixture("board_sample.json")

    def get_league(self):
        return load_fixture("league_sample.json")

    def get_competition_data(self, score_name=None):
        return load_fixture("competition_data_sample.json")

    def get_user_team(self, uid):
        return {"data": {"id": int(uid), "players": [{"id": 1001, "owner": {"price": 8_000_000}}]}}


def test_build_html_contains_sections(tmp_path):
    settings = Settings(user_id="501", league_id="742220", league_name="Pain&Gain",
                        initial_budget=40_000_000, database_url=f"sqlite:///{tmp_path}/t.db")
    engine = init_db(make_engine(settings))
    with session_scope(engine) as s:
        run_ingest(FakeClient(), settings, s, today=date(2026, 8, 8))
        data = load_dashboard_data(s, settings.league_name)
        html = build_dashboard_html(data)

    assert html.startswith("<!doctype html>")
    assert "Econom" in html and "Chollos" in html and "Pain tracker" in html
    assert "Rival A" in html          # nombre de un manager de las standings
    assert "viewport" in html          # responsive (móvil)
