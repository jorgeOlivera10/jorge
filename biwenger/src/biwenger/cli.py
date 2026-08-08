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
def squads(
    user: str = typer.Option("", help="Nombre (o parte) del manager. Vacío = todos."),
) -> None:
    """Lista las plantillas de los managers (última foto guardada)."""
    from sqlalchemy import select
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        last_date = session.scalar(select(models.UserSquad.date).order_by(models.UserSquad.date.desc()))
        if last_date is None:
            console.print("[yellow]No hay plantillas. Ejecuta 'biwenger daily' primero.[/]")
            return
        rows = session.execute(
            select(models.UserSquad, models.User.name, models.Player)
            .join(models.User, models.User.id == models.UserSquad.user_id, isouter=True)
            .join(models.Player, models.Player.id == models.UserSquad.player_id, isouter=True)
            .where(models.UserSquad.date == last_date)
        ).all()

    # Agrupa por manager
    from collections import defaultdict
    by_user: dict[str, list] = defaultdict(list)
    for sq, uname, player in rows:
        by_user[uname or str(sq.user_id)].append((sq, player))

    names = [n for n in by_user if not user or user.lower() in n.lower()]
    if not names:
        console.print(f"[yellow]Ningún manager coincide con '{user}'.[/]")
        return

    for name in sorted(names):
        squad = by_user[name]
        total = sum((p.price or 0) for _, p in squad if p)
        paid = sum((sq.buy_price or 0) for sq, _ in squad)
        table = Table(title=f"{name}  ·  valor €{total:,.0f}  ·  pagado €{paid:,.0f}")
        table.add_column("Jugador", style="cyan")
        table.add_column("Pos", justify="center")
        table.add_column("Equipo")
        table.add_column("Valor", justify="right")
        table.add_column("Pagó", justify="right")
        POS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}
        for sq, p in sorted(squad, key=lambda x: (x[1].price or 0) if x[1] else 0, reverse=True):
            if p is None:
                table.add_row(str(sq.player_id), "?", "—", "—", _money(sq.buy_price))
            else:
                table.add_row(p.name or "—", POS.get(p.position or 0, "?"),
                              p.team_name or "—", _money(p.price), _money(sq.buy_price))
        console.print(table)


@app.command()
def market(
    bank_only: bool = typer.Option(True, help="Mostrar solo los jugadores que vende la BANCA."),
    scout: bool = typer.Option(True, help="Descargar estado/noticias de los jugadores de la banca."),
) -> None:
    """Jugadores en el MERCADO hoy, con estado, si es titular, noticia y puja sugerida.

    Por defecto muestra solo los de la banca (los que te interesan) y descarga su
    ficha (lesión/duda, forma, rendimiento esperado).
    """
    from sqlalchemy import select
    from biwenger.analysis.expected import compute_player_value
    from biwenger.analysis.recommend import RivalCeiling, suggest_bid
    from biwenger.analysis.scouting import player_outlook
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope
    from biwenger.ingest.market import parse_market
    from biwenger.ingest.scout import scout_players

    s = get_settings()
    if not s.user_id or not s.league_id:
        console.print("[red]Faltan X-User / X-League en .env.[/]")
        raise typer.Exit(code=1)

    client = BiwengerClient(s)
    engine = make_engine(s)
    try:
        client.login()
        sales = parse_market(client.get_my_market())
        if not sales:
            console.print("[yellow]No hay jugadores en el mercado ahora (o la API cambió el formato).[/]")
            return
        if bank_only:
            sales = [x for x in sales if not x["seller_id"]]
            if not sales:
                console.print("[yellow]La banca no tiene jugadores en el mercado ahora mismo.[/]")
                return

        with session_scope(engine) as session:
            # Scouting de los jugadores del mercado (acotado a los mostrados).
            if scout:
                ids = [x["player_id"] for x in sales]
                console.print(f"[dim]Analizando {len(ids)} jugadores del mercado…[/]")
                scout_players(client, session, ids, score_name=s.score_default)

            players = {p.id: p for p in session.scalars(select(models.Player)).all()}
            rounds_played = max((pl.played or 0) for pl in players.values()) or None
            last_date = session.scalar(select(models.UserEconomy.date).order_by(models.UserEconomy.date.desc()))
            my_max_bid, rivals = 0, []
            if last_date is not None:
                for ue, u in session.execute(
                    select(models.UserEconomy, models.User)
                    .join(models.User, models.User.id == models.UserEconomy.user_id, isouter=True)
                    .where(models.UserEconomy.date == last_date)
                ).all():
                    if u is not None and u.is_me:
                        my_max_bid = ue.max_bid
                    else:
                        rivals.append(RivalCeiling(ue.user_id, u.name if u else None, ue.max_bid))
            seller_names = {u.id: u.name for u in session.scalars(select(models.User)).all()}

            rows = []
            for sale in sales:
                p = players.get(sale["player_id"])
                if p is None:
                    continue
                rows.append((sale, p, compute_player_value(p, rounds_played), player_outlook(p)))
    finally:
        client.close()

    rows.sort(key=lambda r: r[2].value_ratio, reverse=True)
    table = Table(title="Mercado de hoy" + (" (banca)" if bank_only else ""))
    table.add_column("Jugador", style="cyan")
    table.add_column("Pos", justify="center")
    table.add_column("Precio", justify="right")
    if not bank_only:
        table.add_column("Vende")
    table.add_column("Estado")
    table.add_column("¿Juega?")
    table.add_column("Esperado", justify="right")
    table.add_column("Valor", justify="right", style="bold green")
    table.add_column("Puja sug.", justify="right")
    table.add_column("Nota")
    POS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}
    for sale, p, pv, o in rows:
        sug = suggest_bid(pv, my_max_bid, rivals) if my_max_bid else None
        price = sale["price"] if sale["price"] is not None else p.price
        cells = [p.name or "—", POS.get(p.position or 0, "?"), _money(price)]
        if not bank_only:
            cells.append("banca" if not sale["seller_id"] else seller_names.get(sale["seller_id"], "rival"))
        cells += [
            o.status_label, o.will_play,
            f"{o.expected_ppg}" if o.expected_ppg is not None else "—",
            str(pv.value_ratio),
            _money(sug.suggested_bid) if sug else "—",
            ("[red]⚠ [/]" if o.sell_now else "") + (o.news_title or ""),
        ]
        table.add_row(*cells, style="red" if o.sell_now else None)
    console.print(table)
    console.print(
        "[dim]'Esperado' = pts/partido (temp. actual o pasada). 'Valor' = pts esperados por millón. "
        "Puja sugerida = mercado +15%, limitada por tu puja máxima.[/]"
    )


def _trend(inc: int | None) -> str:
    if not inc:
        return "→"
    return f"[green]↑{inc:,.0f}[/]" if inc > 0 else f"[red]↓{abs(inc):,.0f}[/]"


@app.command()
def team() -> None:
    """Tu plantilla con estado, si va a jugar, rendimiento esperado y alertas de venta."""
    from sqlalchemy import select
    from biwenger.analysis.scouting import player_outlook
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        me = session.scalar(select(models.User).where(models.User.is_me.is_(True)))
        if me is None:
            console.print("[yellow]No sé cuál eres tú aún. Ejecuta 'biwenger daily'.[/]")
            return
        last_date = session.scalar(
            select(models.UserSquad.date).where(models.UserSquad.user_id == me.id)
            .order_by(models.UserSquad.date.desc())
        )
        players = session.scalars(
            select(models.Player)
            .join(models.UserSquad, models.UserSquad.player_id == models.Player.id)
            .where(models.UserSquad.user_id == me.id, models.UserSquad.date == last_date)
        ).all()

    if not players:
        console.print("[yellow]No hay plantilla guardada. Ejecuta 'biwenger daily'.[/]")
        return

    outlooks = sorted((player_outlook(p) for p in players),
                      key=lambda o: (not o.sell_now, -(o.expected_ppg or -1)))
    POS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}
    table = Table(title=f"Tu equipo ({me.name})")
    table.add_column("Jugador", style="cyan")
    table.add_column("Pos", justify="center")
    table.add_column("Estado")
    table.add_column("¿Juega?")
    table.add_column("Esperado", justify="right")
    table.add_column("Precio", justify="right")
    table.add_column("Tend.", justify="right")
    table.add_column("Nota")
    for o in outlooks:
        row_style = "red" if o.sell_now else None
        table.add_row(
            o.name or "—", POS.get(o.position or 0, "?"), o.status_label, o.will_play,
            f"{o.expected_ppg} ({o.basis})" if o.expected_ppg is not None else "sin datos",
            _money(o.price), _trend(o.price_increment),
            ("[bold red]VENDER[/] " if o.sell_now else "") + (o.news_title or ""),
            style=row_style,
        )
    console.print(table)
    console.print("[dim]'Esperado' = puntos/partido (esta temporada o, si no hay, la pasada).[/]")


@app.command()
def alerts() -> None:
    """Solo alertas: jugadores tuyos lesionados/dudas/sancionados o con noticia → vender."""
    from sqlalchemy import select
    from biwenger.analysis.scouting import player_outlook
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        me = session.scalar(select(models.User).where(models.User.is_me.is_(True)))
        if me is None:
            console.print("[yellow]Ejecuta 'biwenger daily' primero.[/]")
            return
        last_date = session.scalar(
            select(models.UserSquad.date).where(models.UserSquad.user_id == me.id)
            .order_by(models.UserSquad.date.desc())
        )
        players = session.scalars(
            select(models.Player)
            .join(models.UserSquad, models.UserSquad.player_id == models.Player.id)
            .where(models.UserSquad.user_id == me.id, models.UserSquad.date == last_date)
        ).all()

    riesgos = [o for o in (player_outlook(p) for p in players) if o.sell_now]
    if not riesgos:
        console.print("[green]✓ Ningún jugador tuyo con alerta. Todo en orden.[/]")
        return
    console.print("[bold red]⚠ Jugadores a revisar / vender:[/]")
    for o in riesgos:
        console.print(f"  • [cyan]{o.name}[/] — {o.status_label}"
                      + (f" · {o.news_title}" if o.news_title else ""))


@app.command()
def recommend(
    top: int = typer.Option(15, help="Número de chollos a mostrar."),
    max_price: int = typer.Option(0, help="Precio máximo (0 = sin límite)."),
    position: int = typer.Option(0, help="Filtrar por posición: 1 PT, 2 DF, 3 MC, 4 DL (0 = todas)."),
    min_games: int = typer.Option(3, help="Partidos mínimos jugados para evitar espejismos."),
    player: int = typer.Option(0, help="ID de jugador para una sugerencia de puja concreta."),
) -> None:
    """Detecta chollos y sugiere puja teniendo en cuenta el techo de tus rivales."""
    from sqlalchemy import select
    from biwenger.analysis.expected import analyze_players
    from biwenger.analysis.recommend import RivalCeiling, rank_chollos, suggest_bid
    from biwenger.db import models
    from biwenger.db.session import make_engine, session_scope

    with session_scope(make_engine()) as session:
        players = session.scalars(select(models.Player)).all()
        if not players:
            console.print("[yellow]No hay jugadores en la BD. Ejecuta 'biwenger ingest' primero.[/]")
            return
        values = analyze_players(list(players))

        # Economía: mi puja máxima y el techo de los rivales.
        last_date = session.scalar(select(models.UserEconomy.date).order_by(models.UserEconomy.date.desc()))
        my_max_bid = 0
        rival_ceilings: list[RivalCeiling] = []
        if last_date is not None:
            rows = session.execute(
                select(models.UserEconomy, models.User)
                .join(models.User, models.User.id == models.UserEconomy.user_id, isouter=True)
                .where(models.UserEconomy.date == last_date)
            ).all()
            for ue, user in rows:
                if user is not None and user.is_me:
                    my_max_bid = ue.max_bid
                else:
                    rival_ceilings.append(
                        RivalCeiling(user_id=ue.user_id, name=(user.name if user else None), max_bid=ue.max_bid)
                    )

        by_id = {v.player_id: v for v in values}

    # Sugerencia de puja para un jugador concreto.
    if player:
        target = by_id.get(player)
        if target is None:
            console.print(f"[red]Jugador {player} no encontrado.[/]")
            raise typer.Exit(code=1)
        if not my_max_bid:
            console.print("[yellow]Sin economía calculada: la sugerencia usará solo el mercado.[/]")
        sug = suggest_bid(target, my_max_bid, rival_ceilings)
        t = Table(title=f"Sugerencia de puja — {target.name}")
        t.add_column("Concepto", style="cyan")
        t.add_column("Valor", justify="right")
        t.add_row("Precio mercado", _money(sug.market_price))
        t.add_row("Puja de valor (+15%)", _money(sug.value_bid))
        t.add_row("Para superar rivales", _money(sug.bid_to_beat_rivals))
        t.add_row("Tu puja máxima", _money(sug.my_max_bid))
        if sug.top_rival:
            t.add_row("Mayor rival", f"{sug.top_rival.name}: {_money(sug.top_rival.max_bid)}")
        t.add_row("[bold]Puja sugerida[/]", f"[bold]{_money(sug.suggested_bid)}[/]")
        console.print(t)
        console.print(f"[dim]{sug.note}[/]")
        return

    # Ranking de chollos.
    chollos = rank_chollos(
        values,
        min_games=min_games,
        max_price=max_price or None,
        position=position or None,
        top=top,
    )
    if not chollos:
        console.print("[yellow]No hay chollos con esos filtros (¿temporada sin empezar?).[/]")
        return

    table = Table(title="Chollos — mejor relación puntos/precio")
    table.add_column("Jugador", style="cyan")
    table.add_column("Pos", justify="center")
    table.add_column("Equipo")
    table.add_column("Precio", justify="right")
    table.add_column("Pts/part.", justify="right")
    table.add_column("Esperados", justify="right")
    table.add_column("Valor (pts/M€)", justify="right", style="bold green")
    for c in chollos:
        table.add_row(
            c.name or "—", c.position_name, c.team_name or "—",
            _money(c.price), str(c.points_per_match), str(c.expected_points), str(c.value_ratio),
        )
    console.print(table)
    console.print(
        "[dim]Valor = puntos esperados por millón. Esperados = pts/partido × fiabilidad × tendencia.[/]"
    )


@app.command()
def daily() -> None:
    """Job diario: ingesta + informe del día en reports/ (idempotente)."""
    from biwenger.jobs.daily import run_daily

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

    path, summary = run_daily(client, s)
    client.close()
    console.print(
        f"[green]✓ Informe del día:[/] {path}  "
        f"([cyan]{summary['movements_new']}[/] movimientos nuevos)"
    )
    console.print(f"[green]✓ Dashboard HTML:[/] {summary.get('html_path', '—')}")


@app.command()
def html(
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Abrir en el navegador al terminar."),
) -> None:
    """Genera un dashboard HTML autocontenido (dashboard.html) para ver en cualquier sitio."""
    import webbrowser
    from biwenger.config import PROJECT_ROOT
    from biwenger.db.session import make_engine, session_scope
    from biwenger.webreport import build_dashboard_html, load_dashboard_data

    s = get_settings()
    out = PROJECT_ROOT / "reports" / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    with session_scope(make_engine(s)) as session:
        data = load_dashboard_data(session, s.league_name)
    if not data["economy"]:
        console.print("[yellow]No hay datos. Ejecuta 'biwenger daily' primero.[/]")
        raise typer.Exit(code=1)
    out.write_text(build_dashboard_html(data), encoding="utf-8")
    console.print(f"[green]✓ Dashboard generado:[/] {out}")
    console.print("[dim]Ábrelo con doble clic, o envíatelo al móvil (WhatsApp/Drive) para verlo donde sea.[/]")
    if open_browser:
        try:
            webbrowser.open(out.as_uri())
        except Exception:  # noqa: BLE001
            pass


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
    all_zero = set(results.values()) == {0}
    if all_zero:
        console.print(
            "\n[cyan]ℹ Todos los sistemas dan 0 puntos:[/] la temporada aún no ha empezado "
            "(no hay partidos jugados). No se puede comparar todavía; vuelve a probar tras la "
            "1ª jornada. El score de tu liga (AS=5) es correcto de todos modos."
        )
    elif distinct <= 1 and len(results) > 1:
        console.print(
            "\n[yellow]⚠ Los sistemas devuelven los MISMOS totales:[/] probablemente algún "
            "id de 'score' no es correcto. Prueba otros valores en BIWENGER_SCORE_*."
        )
    else:
        console.print("\n[green]✓ Los sistemas de puntuación devuelven datos distintos: IDs OK.[/]")
    client.close()


if __name__ == "__main__":  # pragma: no cover
    app()
