"""Test del job diario: escribe un informe y es idempotente (BD temporal, mock)."""

from __future__ import annotations

from datetime import date

from biwenger.config import Settings
from biwenger.db.session import make_engine
from biwenger.jobs.daily import build_report, run_daily
from tests.conftest import load_fixture


class FakeClient:
    def get_full_board(self):
        return load_fixture("board_sample.json")

    def get_league(self):
        return load_fixture("league_sample.json")

    def get_competition_data(self, score_name=None):
        return load_fixture("competition_data_sample.json")


def _settings(tmp_path) -> Settings:
    return Settings(
        user_id="501", league_id="742220",
        initial_budget=40_000_000, bid_team_value_factor=0.25,
        database_url=f"sqlite:///{tmp_path}/test.db",
    )


def test_run_daily_writes_report(tmp_path):
    settings = _settings(tmp_path)
    engine = make_engine(settings)
    reports = tmp_path / "reports"

    path, summary = run_daily(
        FakeClient(), settings, engine, today=date(2026, 8, 8), reports_dir=reports
    )
    assert path.exists()
    assert path.name == "2026-08-08.md"
    content = path.read_text(encoding="utf-8")
    assert "# Informe Biwenger — 2026-08-08" in content
    assert "Economía estimada" in content
    assert summary["managers"] == 3


def test_run_daily_is_idempotent(tmp_path):
    settings = _settings(tmp_path)
    engine = make_engine(settings)
    reports = tmp_path / "reports"

    _, s1 = run_daily(FakeClient(), settings, engine, today=date(2026, 8, 8), reports_dir=reports)
    _, s2 = run_daily(FakeClient(), settings, engine, today=date(2026, 8, 9), reports_dir=reports)
    assert s1["movements_new"] == 4
    assert s2["movements_new"] == 0   # nada nuevo la segunda vez


def test_build_report_contains_chollos_section():
    summary = {
        "date": date(2026, 8, 8),
        "movements_new": 2, "movements_total": 10, "managers": 3,
        "players_new": 4, "unknown_types": {}, "economy": [], "pain": [],
    }

    class _C:
        name, position_name, price = "Chollo", "DL", 3_000_000
        points_per_match, expected_points, value_ratio = 7.0, 7.0, 2.33

    report = build_report(summary, [_C()])
    assert "Chollos del día" in report
    assert "Chollo" in report
