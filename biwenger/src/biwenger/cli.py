"""Interfaz de línea de comandos (CLI) de biwenger-analyzer.

En esta Fase 1 solo hay comandos de diagnóstico. Los comandos de ingesta,
economía, recomendaciones y job diario se añaden en fases posteriores.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from biwenger import __version__
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


if __name__ == "__main__":  # pragma: no cover
    app()
