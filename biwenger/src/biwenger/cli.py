"""Interfaz de línea de comandos (CLI) de biwenger-analyzer.

En esta Fase 1 solo hay comandos de diagnóstico. Los comandos de ingesta,
economía, recomendaciones y job diario se añaden en fases posteriores.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from biwenger import __version__
from biwenger.api.client import BiwengerAPIError, BiwengerClient
from biwenger.api.parse import extract_players, player_points
from biwenger.config import get_settings
from biwenger.logging_setup import setup_logging

app = typer.Typer(
    add_completion=False,
    help="Herramienta de análisis para tu liga de Biwenger (fantasy LaLiga).",
)
console = Console()


@app.callback()
def _main() -> None:
    """Configura el logging antes de ejecutar cualquier comando."""
    settings = get_settings()
    setup_logging(settings.log_level)


@app.command()
def version() -> None:
    """Muestra la versión de la herramienta."""
    console.print(f"biwenger-analyzer [bold cyan]v{__version__}[/]")


@app.command()
def config() -> None:
    """Muestra la configuración cargada (ocultando credenciales)."""
    s = get_settings()

    def mask(value: str) -> str:
        if not value:
            return "[red]— sin definir —[/]"
        return "•" * 6 + f" ([dim]{len(value)} chars[/])"

    table = Table(title="Configuración de biwenger-analyzer", show_lines=False)
    table.add_column("Clave", style="cyan", no_wrap=True)
    table.add_column("Valor")

    table.add_row("Liga", s.league_name or "—")
    table.add_row("Email", mask(s.email))
    table.add_row("Password", mask(s.password))
    table.add_row("X-User", mask(s.user_id))
    table.add_row("X-League", mask(s.league_id))
    table.add_row("X-Version", mask(s.version))
    table.add_row("Scores", str(s.scores) + f"  (default: {s.score_default})")
    table.add_row("Presupuesto inicial", f"{s.initial_budget:,.0f}")
    table.add_row("Factor puja (valor equipo)", str(s.bid_team_value_factor))
    table.add_row("Base de datos", s.resolved_database_url())
    table.add_row("Throttle (s)", str(s.min_request_interval))
    table.add_row("Cache TTL (s)", str(s.cache_ttl))

    console.print(table)

    missing = [
        name
        for name, val in {
            "email": s.email,
            "password": s.password,
            "X-User": s.user_id,
            "X-League": s.league_id,
            "X-Version": s.version,
        }.items()
        if not val
    ]
    if missing:
        console.print(
            f"\n[yellow]⚠ Faltan por rellenar en .env:[/] {', '.join(missing)}"
        )
    else:
        console.print("\n[green]✓ Configuración completa.[/]")


@app.command(name="init-db")
def init_db_cmd() -> None:
    """Crea la base de datos y su esquema (idempotente)."""
    from biwenger.db.session import init_db

    s = get_settings()
    init_db()
    console.print(f"[green]✓ Base de datos lista:[/] {s.resolved_database_url()}")


def _money(n: float | int | None) -> str:
    if n is None:
        return "—"
    return f"€{n:,.0f}"


@app.command()
def ingest() -> None:
    """Ingesta diaria: tablón + liga, reconstruye economía y Pain tracker (idempotente)."""
    from biwenger.db.session import init_db, session_scope
    from biwenger.ingest.runner import run_ingest

    s = get_settings()
    if not s.user_id or not s.league_id:
        console.print("[red]Faltan X-User / X-League en .env.[/] Ejecuta 'biwenger config'.")
        raise typer.Exit(code=1)

    client = BiwengerClient(s)
    try:
        client.login()
    except BiwengerAPIError as exc:
        console.print(f"[red]✗ Login: {exc}[/]")
        raise typer.Exit(code=1)

    engine = init_db()
    with session_scope(engine) as session:
        summary = run_ingest(client, s, session)
    client.close()

    console.print(
        f"[green]✓ Ingesta OK[/] — {summary['movements_new']} movimientos nuevos "
        f"(de {summary['movements_total']}), {summary['managers']} managers."
    )
    if summary["unknown_types"]:
        console.print(
            f"[yellow]⚠ Tipos de movimiento no reconocidos (posibles cesiones/retos):[/] "
            f"{summary['unknown_types']} — incluidos en el saldo como estimación."
        )
    _print_economy(summary["economy"])


def _print_economy(economies) -> None:
    table = Table(title="Economía estimada por manager")
    table.add_column("Manager", style="cyan")
    table.add_column("Saldo", justify="right")
    table.add_column("Valor equipo", justify="right")
    table.add_column("Puja máx.", justify="right", style="bold")
    table.add_column("Total", justify="right")
    table.add_column("Avisos")
    for e in economies:
        table.add_row(
            e.name or str(e.user_id),
            _money(e.cash),
            _money(e.team_value),
            _money(e.max_bid),
            _money(e.cash + e.team_value),
            "; ".join(e.flags) if e.flags else "",
        )
    console.print(table)
    console.print(
        "[dim]Puja máxima = saldo + 0.25 × valor de equipo. ESTIMACIÓN: ver README "
        "(primas, cesiones, liquidez guardada).[/]"
    )


@app.command()
def economy() -> None:
    """Muestra la última economía estimada guardada en la BD."""
    from sqlalchemy import select
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        last_date = session.scalar(select(models.UserEconomy.date).order_by(models.UserEconomy.date.desc()))
        if last_date is None:
            console.print("[yellow]No hay datos. Ejecuta 'biwenger ingest' primero.[/]")
            return
        rows = session.execute(
            select(models.UserEconomy, models.User.name)
            .join(models.User, models.User.id == models.UserEconomy.user_id, isouter=True)
            .where(models.UserEconomy.date == last_date)
        ).all()

    class _E:  # adaptador ligero para reutilizar _print_economy
        def __init__(self, ue, name):
            self.user_id, self.name = ue.user_id, name
            self.cash, self.team_value, self.max_bid = ue.cash, ue.team_value, ue.max_bid
            self.flags = []

    economies = sorted((_E(ue, name) for ue, name in rows), key=lambda e: e.cash + e.team_value, reverse=True)
    console.print(f"[dim]Snapshot: {last_date}[/]")
    _print_economy(economies)


@app.command()
def pain() -> None:
    """Muestra el marcador de dinero REAL (Pain tracker) desde la BD."""
    from collections import defaultdict
    from sqlalchemy import select
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        rows = session.execute(
            select(models.RealMoneyLedger, models.User.name)
            .join(models.User, models.User.id == models.RealMoneyLedger.user_id, isouter=True)
        ).all()

    if not rows:
        console.print("[yellow]No hay datos de jornadas. Ejecuta 'biwenger ingest' primero.[/]")
        return

    pen: dict[int, float] = defaultdict(float)
    resets: dict[int, int] = defaultdict(int)
    names: dict[int, str] = {}
    for led, name in rows:
        names[led.user_id] = name or str(led.user_id)
        if led.concept == "penalty":
            pen[led.user_id] += led.amount_eur
        elif led.concept == "deposit_reset":
            resets[led.user_id] += 1

    table = Table(title="Pain tracker — dinero REAL (€)")
    table.add_column("Manager", style="cyan")
    table.add_column("Pérdidas €", justify="right", style="bold red")
    table.add_column("Re-fianzas (regla 15)", justify="right")
    for uid in sorted(pen, key=lambda u: pen[u], reverse=True):
        table.add_row(names[uid], f"{pen[uid]:.0f} €", str(resets.get(uid, 0)))
    console.print(table)
    console.print("[dim]Castigo por jornada: último 3€, penúltimo 2€, antepenúltimo 1€.[/]")


@app.command()
def verify(
    login: bool = typer.Option(
        False, "--login", help="Hace login con las credenciales del .env antes de consultar."
    ),
) -> None:
    """Llamada REAL al endpoint de datos de LaLiga para verificar los IDs de 'score'.

    Consulta el endpoint público de competición para cada sistema de puntuación
    configurado (sofascore, as) y compara el nº de jugadores y los puntos totales.
    Si los totales difieren entre sistemas, los IDs de score son correctos.
    """
    s = get_settings()
    client = BiwengerClient(s)
    if login:
        try:
            client.login()
        except BiwengerAPIError as exc:
            console.print(f"[red]✗ Login: {exc}[/]")
            raise typer.Exit(code=1)

    table = Table(title="Verificación de la API de Biwenger")
    table.add_column("Sistema", style="cyan")
    table.add_column("score id", justify="right")
    table.add_column("Jugadores", justify="right")
    table.add_column("Σ puntos", justify="right")
    table.add_column("Top jugador (pts)")

    results: dict[str, int] = {}
    ok = True
    for name, score in s.scores.items():
        try:
            raw = client.get_competition_data(name)
            players = extract_players(raw)
            total = sum(player_points(p) for p in players)
            top = max(players, key=player_points, default={})
            top_desc = (
                f"{top.get('name', '—')} ({player_points(top)})" if top else "—"
            )
            table.add_row(name, str(score), str(len(players)), f"{total:,}", top_desc)
            results[name] = total
        except Exception as exc:  # noqa: BLE001 - queremos reportar cualquier fallo real
            ok = False
            table.add_row(name, str(score), "[red]ERROR[/]", "—", f"[red]{exc}[/]")

    console.print(table)

    if not ok:
        console.print(
            "\n[yellow]⚠ Alguna consulta falló.[/] Si es un bloqueo de red, ejecútalo en tu "
            "máquina local. Si es 4xx, revisa los IDs de score o las cabeceras en .env."
        )
        raise typer.Exit(code=1)

    distinct = len(set(results.values()))
    if distinct <= 1 and len(results) > 1:
        console.print(
            "\n[yellow]⚠ Los sistemas devuelven los MISMOS totales:[/] probablemente algún "
            "id de 'score' no es correcto. Prueba otros valores en BIWENGER_SCORE_*."
        )
    else:
        console.print("\n[green]✓ Los sistemas de puntuación devuelven datos distintos: IDs OK.[/]")
    client.close()


if __name__ == "__main__":  # pragma: no cover
    app()
