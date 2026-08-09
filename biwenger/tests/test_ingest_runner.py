"""Test de integración del orquestador de ingesta (BD real en fichero temporal,
cliente mockeado — sin red). Verifica idempotencia."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from biwenger.config import Settings
from biwenger.db import models
from biwenger.db.session import init_db, make_engine, session_scope
from biwenger.ingest.runner import run_ingest
from tests.conftest import load_fixture


class FakeClient:
    """Cliente falso que devuelve fixtures en lugar de llamar a la API."""

    def get_full_board(self):
        return load_fixture("board_sample.json")

    def get_league(self):
        return load_fixture("league_sample.json")

    def get_competition_data(self, score_name=None):
        return load_fixture("competition_data_sample.json")


class FakeClientSquads(FakeClient):
    """FakeClient que además sirve las plantillas (para el coste inicial)."""

    COST = {501: 26_580_000, 502: 30_000_000, 503: 20_000_000}

    def __init__(self):
        self.team_calls = 0

    def get_user_team(self, uid):
        self.team_calls += 1
        uid = int(uid)
        return {"data": {"id": uid, "name": "x",
                         "players": [{"id": uid * 10, "owner": {"price": self.COST[uid]}}]}}


class FakeClientWithAccount(FakeClient):
    """Como FakeClient pero además expone /account con mi saldo real en la liga."""

    def get_account(self):
        return {
            "status": 200,
            "data": {
                "account": {"id": 1596507},
                "leagues": [
                    {"id": 742220, "name": "Pain&Gain",
                     "user": {"id": 501, "name": "Jorge", "balance": 13_420_000}},
                ],
            },
        }


def _settings(tmp_path) -> Settings:
    return Settings(
        user_id="501",
        league_id="742220",
        initial_budget=40_000_000,
        bid_team_value_factor=0.25,
        database_url=f"sqlite:///{tmp_path}/test.db",
    )


def test_ingest_populates_and_is_idempotent(tmp_path):
    settings = _settings(tmp_path)
    engine = init_db(make_engine(settings))

    with session_scope(engine) as s:
        summary1 = run_ingest(FakeClient(), settings, s, today=date(2026, 8, 8))

    # Primera pasada: 3 movimientos de compraventa + 1 cesión = 4 nuevos
    assert summary1["movements_new"] == 4
    assert summary1["managers"] == 3
    assert summary1["unknown_types"] == {"loan": 1}   # detecta y avisa

    # Segunda pasada idéntica: nada nuevo (idempotente)
    with session_scope(engine) as s:
        summary2 = run_ingest(FakeClient(), settings, s, today=date(2026, 8, 8))
    assert summary2["movements_new"] == 0

    # Primera pasada ingiere también los 4 jugadores del fixture de competición.
    assert summary1["players_new"] == 4
    assert summary2["players_new"] == 0   # upsert idempotente

    # La BD no ha duplicado filas
    with session_scope(engine) as s:
        assert s.scalar(select(func.count()).select_from(models.Movement)) == 4
        assert s.scalar(select(func.count()).select_from(models.User)) == 3
        assert s.scalar(select(func.count()).select_from(models.Player)) == 4
        # economía guardada para los 3 managers
        assert s.scalar(select(func.count()).select_from(models.UserEconomy)) == 3
        # Jorge (501) marcado como 'yo'
        me = s.get(models.User, 501)
        assert me.is_me is True


def test_ingest_computes_expected_cash_for_me(tmp_path):
    settings = _settings(tmp_path)
    engine = init_db(make_engine(settings))
    with session_scope(engine) as s:
        run_ingest(FakeClient(), settings, s, today=date(2026, 8, 8))
        ue = s.scalar(select(models.UserEconomy).where(models.UserEconomy.user_id == 501))
        # Sin /account: cash estimado = 40M − 30M valor equipo + 1M prima = 11M
        assert ue.cash == 11_000_000
        assert ue.max_bid == 18_500_000


def test_rival_cash_is_budget_minus_team_value(tmp_path):
    settings = _settings(tmp_path)
    engine = init_db(make_engine(settings))
    client = FakeClientSquads()

    with session_scope(engine) as s:
        run_ingest(client, settings, s, today=date(2026, 8, 8))
        # Rival B (503): 40M − 10M (valor equipo de standings) + 0.3M cesión = 30.3M
        ue = s.scalar(select(models.UserEconomy).where(models.UserEconomy.user_id == 503))
        assert ue.cash == 30_300_000
        # Las plantillas se guardan para las pestañas (1 jugador x 3 managers).
        assert s.scalar(select(func.count()).select_from(models.UserSquad)) == 3

    assert client.team_calls == 3   # una plantilla por manager


def test_ingest_uses_exact_balance_from_account(tmp_path):
    settings = _settings(tmp_path)
    engine = init_db(make_engine(settings))
    with session_scope(engine) as s:
        run_ingest(FakeClientWithAccount(), settings, s, today=date(2026, 8, 8))
        ue = s.scalar(select(models.UserEconomy).where(models.UserEconomy.user_id == 501))
        # Con /account: usa mi saldo EXACTO (13.42M), no la estimación.
        assert ue.cash == 13_420_000
        assert ue.max_bid == 13_420_000 + 7_500_000
