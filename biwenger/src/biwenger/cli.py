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
