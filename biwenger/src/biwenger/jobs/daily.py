"""Job diario: ingesta idempotente + informe del día en Markdown.

Poléa el tablón y la liga, actualiza la BD (solo lo nuevo) y deja un informe
fechado en reports/. Pensado para lanzarse por cron/Task Scheduler/GitHub Action.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from biwenger.analysis.expected import analyze_players
from biwenger.analysis.recommend import rank_chollos
from biwenger.config import PROJECT_ROOT, Settings
from biwenger.db import models
from biwenger.db.session import init_db, session_scope
from biwenger.ingest.runner import run_ingest
from biwenger.logging_setup import get_logger

log = get_logger(__name__)


def _money(n: float | int | None) -> str:
    return "—" if n is None else f"€{n:,.0f}"


def _load_chollos_from_db(session: Session, *, top: int = 10) -> list:
    players = session.scalars(select(models.Player)).all()
    if not players:
        return []
    values = analyze_players(list(players))
    return rank_chollos(values, min_games=1, top=top)


def _ingest_market(client: Any, settings: Settings, session: Session, today: date) -> None:
    """Ingiere el mercado del día (banca) y scoutea esos jugadores. Defensivo."""
    from biwenger.ingest.market import parse_market
    from biwenger.ingest.scout import scout_players
    from biwenger.ingest import store

    try:
        sales = parse_market(client.get_my_market())
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo leer el mercado: %s", exc)
        return
    store.store_market_daily(session, today, sales)
    bank_ids = [x["player_id"] for x in sales if not x["seller_id"]][:60]
    if bank_ids and hasattr(client, "get_player_detail"):
        scout_players(client, session, bank_ids, score_name=settings.score_default, today=today)


def build_report(summary: dict[str, Any], chollos: list) -> str:
    """Construye el informe del día en Markdown a partir del resumen de ingesta."""
    lines: list[str] = []
    d = summary["date"]
    lines.append(f"# Informe Biwenger — {d}")
    lines.append("")
    lines.append(
        f"- Movimientos nuevos: **{summary['movements_new']}** "
        f"(total en tablón: {summary['movements_total']})"
    )
    lines.append(f"- Managers: **{summary['managers']}**  ·  Jugadores nuevos: {summary.get('players_new', 0)}")
    if summary["unknown_types"]:
        lines.append(
            f"- ⚠️ Tipos de movimiento sin reconocer (posibles cesiones/retos): "
            f"`{summary['unknown_types']}` — incluidos como estimación."
        )
    lines.append("")

    # Economía
    lines.append("## Economía estimada (saldo · valor · puja máxima)")
    lines.append("")
    lines.append("| Manager | Saldo | Valor equipo | Puja máx. | Total |")
    lines.append("|---|--:|--:|--:|--:|")
    for e in summary["economy"]:
        lines.append(
            f"| {e.name or e.user_id} | {_money(e.cash)} | {_money(e.team_value)} "
            f"| {_money(e.max_bid)} | {_money(e.cash + e.team_value)} |"
        )
    lines.append("")
    lines.append("> Puja máxima = saldo + 0.25 × valor de equipo. Es una **estimación**.")
    lines.append("")

    # Chollos
    if chollos:
        lines.append("## Chollos del día (mejor relación puntos/precio)")
        lines.append("")
        lines.append("| Jugador | Pos | Precio | Pts/partido | Esperados | Valor (pts/M€) |")
        lines.append("|---|:--:|--:|--:|--:|--:|")
        for c in chollos:
            lines.append(
                f"| {c.name} | {c.position_name} | {_money(c.price)} | {c.points_per_match} "
                f"| {c.expected_points} | {c.value_ratio} |"
            )
        lines.append("")

    # Pain
    if summary["pain"]:
        lines.append("## Pain tracker (dinero real €)")
        lines.append("")
        lines.append("| Manager | Pérdidas € | Re-fianzas |")
        lines.append("|---|--:|--:|")
        for t in summary["pain"]:
            lines.append(f"| {t.user_name or t.user_id} | {t.total_eur:.0f} € | {t.deposit_resets} |")
        lines.append("")

    return "\n".join(lines)


def run_daily(
    client: Any,
    settings: Settings,
    engine: Engine | None = None,
    *,
    today: date | None = None,
    reports_dir: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Ejecuta la ingesta del día y escribe el informe. Devuelve (ruta, resumen)."""
    today = today or date.today()
    engine = init_db(engine)  # crea el engine por defecto si engine is None
    reports_dir = reports_dir or (PROJECT_ROOT / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    from biwenger.webreport import build_dashboard_html, load_dashboard_data

    with session_scope(engine) as session:
        summary = run_ingest(client, settings, session, today=today)
        _ingest_market(client, settings, session, today)
        chollos = _load_chollos_from_db(session)
        dashboard_html = build_dashboard_html(load_dashboard_data(session, settings.league_name))

    report = build_report(summary, chollos)
    path = reports_dir / f"{today.isoformat()}.md"
    path.write_text(report, encoding="utf-8")

    # Dashboard HTML autocontenido (para verlo en cualquier navegador / móvil).
    html_path = reports_dir / "dashboard.html"
    html_path.write_text(dashboard_html, encoding="utf-8")
    summary["html_path"] = str(html_path)

    log.info("Informe del día en %s ; dashboard en %s", path, html_path)
    return path, summary
