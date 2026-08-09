"""Genera un dashboard en un ÚNICO fichero HTML autocontenido (sin servidor).

Se abre en cualquier navegador (PC o móvil), no necesita instalar nada ni estar
en el mismo WiFi: es un archivo que puedes enviarte al teléfono o publicar en
cualquier hosting estático (GitHub Pages, etc.).
"""

from __future__ import annotations

import html
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from biwenger.analysis.expected import analyze_players
from biwenger.analysis.recommend import rank_chollos
from biwenger.analysis.scouting import player_outlook
from biwenger.db import models

_POS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}


def _money(n: Any) -> str:
    try:
        return f"€{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def load_dashboard_data(session: Session, league_name: str = "Mi Liga") -> dict[str, Any]:
    """Reúne desde la BD todo lo que muestra el dashboard."""
    users = {u.id: u for u in session.scalars(select(models.User)).all()}
    me = next((u for u in users.values() if u.is_me), None)

    last_econ = session.scalar(select(models.UserEconomy.date).order_by(models.UserEconomy.date.desc()))
    economy = []
    if last_econ is not None:
        for ue in session.scalars(select(models.UserEconomy).where(models.UserEconomy.date == last_econ)):
            u = users.get(ue.user_id)
            economy.append({
                "manager": u.name if u else str(ue.user_id),
                "cash": ue.cash, "team_value": ue.team_value, "max_bid": ue.max_bid,
                "total": ue.cash + ue.team_value, "me": bool(u and u.is_me),
            })
    economy.sort(key=lambda r: r["total"], reverse=True)

    players = list(session.scalars(select(models.Player)))
    chollos = rank_chollos(analyze_players([_pdict(p) for p in players]), min_games=1, top=20)

    my_team = []
    if me is not None:
        last_sq = session.scalar(
            select(models.UserSquad.date).where(models.UserSquad.user_id == me.id)
            .order_by(models.UserSquad.date.desc())
        )
        if last_sq is not None:
            mine = session.scalars(
                select(models.Player).join(
                    models.UserSquad, models.UserSquad.player_id == models.Player.id
                ).where(models.UserSquad.user_id == me.id, models.UserSquad.date == last_sq)
            ).all()
            my_team = [player_outlook(p) for p in mine]

    last_sq_all = session.scalar(select(models.UserSquad.date).order_by(models.UserSquad.date.desc()))
    squads: dict[str, list] = {}
    if last_sq_all is not None:
        for sq, p in session.execute(
            select(models.UserSquad, models.Player)
            .join(models.Player, models.Player.id == models.UserSquad.player_id, isouter=True)
            .where(models.UserSquad.date == last_sq_all)
        ).all():
            name = users[sq.user_id].name if sq.user_id in users else str(sq.user_id)
            squads.setdefault(name, []).append((sq, p))

    pain: dict[int, dict] = {}
    for led in session.scalars(select(models.RealMoneyLedger)):
        u = users.get(led.user_id)
        row = pain.setdefault(led.user_id, {"manager": u.name if u else str(led.user_id),
                                            "loss": 0.0, "resets": 0})
        if led.concept == "penalty":
            row["loss"] += led.amount_eur
        elif led.concept == "deposit_reset":
            row["resets"] += 1

    market = _load_market(session, players, economy, users)

    return {
        "league": league_name, "me": me.name if me else None,
        "date": str(last_econ) if last_econ else None,
        "economy": economy, "my_team": my_team, "chollos": chollos, "market": market,
        "squads": squads, "pain": sorted(pain.values(), key=lambda r: r["loss"], reverse=True),
    }


def _load_market(session: Session, players: list, economy: list, users: dict) -> list[dict]:
    """Mercado del día (banca) con veredicto, valor y puja sugerida."""
    from biwenger.analysis.expected import compute_player_value
    from biwenger.analysis.recommend import RivalCeiling, suggest_bid

    last_mkt = session.scalar(select(models.MarketDaily.date).order_by(models.MarketDaily.date.desc()))
    if last_mkt is None:
        return []
    rounds_played = max((p.played or 0) for p in players) if players else 0
    my_max_bid, rivals = 0, []
    for r in economy:
        if r.get("me"):
            my_max_bid = r["max_bid"]
        else:
            rivals.append(RivalCeiling(0, r["manager"], r["max_bid"]))

    rows = session.execute(
        select(models.MarketDaily, models.Player)
        .join(models.Player, models.Player.id == models.MarketDaily.player_id, isouter=True)
        .where(models.MarketDaily.date == last_mkt)
    ).all()
    out = []
    for md, p in rows:
        if p is None or md.seller_id:   # solo banca
            continue
        pv = compute_player_value(_pdict(p), rounds_played or None)
        o = player_outlook(p)
        sug = suggest_bid(pv, my_max_bid, rivals) if my_max_bid else None
        out.append({
            "name": p.name, "pos": _POS.get(p.position or 0, "?"),
            "price": md.price if md.price is not None else p.price,
            "status": o.status_label, "will_play": o.will_play,
            "expected": o.expected_ppg, "value_ratio": pv.value_ratio,
            "suggested": (sug.suggested_bid if sug else None),
            "sell_now": o.sell_now, "news": o.note,
        })
    out.sort(key=lambda r: r["value_ratio"], reverse=True)
    return out


def _pdict(p) -> dict:
    return {"id": p.id, "name": p.name, "position": p.position, "team_name": p.team_name,
            "price": p.price or 0, "price_increment": p.price_increment or 0,
            "total_points": p.total_points, "played": p.played,
            "points_home": p.points_home, "played_home": p.played_home,
            "points_away": p.points_away, "played_away": p.played_away, "status": p.status}


def _e(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _table(headers: list[str], rows: list[list[str]], row_classes: list[str] | None = None) -> str:
    thead = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for i, r in enumerate(rows):
        cls = f' class="{row_classes[i]}"' if row_classes else ""
        body.append("<tr" + cls + ">" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    return f'<div class="tw"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def build_dashboard_html(data: dict[str, Any]) -> str:
    """Construye el HTML completo (autocontenido) del dashboard."""
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    me = _e(data.get("me") or "")
    league = _e(data.get("league") or "Biwenger")

    # Alertas
    alerts = [o for o in data["my_team"] if o.sell_now]
    alert_html = ""
    if alerts:
        items = " · ".join(f"{_e(o.name)} ({_e(o.status_label)})" for o in alerts)
        alert_html = f'<div class="alert">🚨 A revisar / vender: {items}</div>'

    # Economía
    econ_rows, econ_cls = [], []
    for r in data["economy"]:
        econ_rows.append([_e(r["manager"]), _money(r["cash"]), _money(r["team_value"]),
                          f'<b>{_money(r["max_bid"])}</b>', _money(r["total"])])
        econ_cls.append("me" if r["me"] else "")
    econ = _table(["Manager", "Saldo", "Valor equipo", "Puja máx.", "Total"], econ_rows, econ_cls)

    # Mi equipo
    team_rows, team_cls = [], []
    for o in sorted(data["my_team"], key=lambda o: (not o.sell_now, -(o.expected_ppg or -1))):
        trend = "→" if not o.price_increment else (f"↑{abs(o.price_increment):,.0f}".replace(",", ".")
                                                   if o.price_increment > 0 else f"↓{abs(o.price_increment):,.0f}".replace(",", "."))
        team_rows.append([
            _e(o.name), _POS.get(o.position or 0, "?"), _e(o.status_label), _e(o.will_play),
            (f"{o.expected_ppg}" if o.expected_ppg is not None else "—"),
            _money(o.price), trend,
            ("<b>VENDER</b> " if o.sell_now else "") + _e(o.note),
        ])
        team_cls.append("sell" if o.sell_now else "")
    team = _table(["Jugador", "Pos", "Estado", "¿Juega?", "Esperado", "Precio", "Tend.", "Nota"],
                  team_rows, team_cls) if team_rows else "<p class='muted'>Sin plantilla. Ejecuta <code>biwenger daily</code>.</p>"

    # Mercado (banca)
    mkt_rows, mkt_cls = [], []
    for m in data.get("market", []):
        mkt_rows.append([
            _e(m["name"]), m["pos"], _money(m["price"]), _e(m["status"]), _e(m["will_play"]),
            (f"{m['expected']}" if m["expected"] is not None else "—"),
            f'<b>{m["value_ratio"]}</b>',
            _money(m["suggested"]) if m["suggested"] else "—",
            ("<b>⚠</b> " if m["sell_now"] else "") + _e(m["news"]),
        ])
        mkt_cls.append("sell" if m["sell_now"] else "")
    market = _table(["Jugador", "Pos", "Precio", "Estado", "¿Juega?", "Esperado", "Valor", "Puja sug.", "Nota"],
                    mkt_rows, mkt_cls) if mkt_rows \
        else "<p class='muted'>La banca no tiene jugadores en el mercado ahora (o aún no se ha ingerido).</p>"

    # Chollos
    chollo_rows = [[_e(c.name), c.position_name, _e(c.team_name or "—"), _money(c.price),
                    str(c.points_per_match), str(c.expected_points), f'<b>{c.value_ratio}</b>']
                   for c in data["chollos"]]
    chollos = _table(["Jugador", "Pos", "Equipo", "Precio", "Pts/part.", "Esperados", "Valor (pts/M€)"],
                     chollo_rows) if chollo_rows else "<p class='muted'>Sin chollos con datos todavía (¿temporada sin empezar?).</p>"

    # Plantillas (colapsables)
    squads_html = []
    for name in sorted(data["squads"]):
        rows = sorted(data["squads"][name], key=lambda x: (x[1].price or 0) if x[1] else 0, reverse=True)
        r = [[_e(p.name) if p else _e(sq.player_id), _POS.get((p.position if p else 0) or 0, "?"),
              _e(p.team_name or "—") if p else "—", _money(p.price if p else None), _money(sq.buy_price)]
             for sq, p in rows]
        squads_html.append(
            f"<details><summary>{_e(name)} "
            f"<span class='muted'>({len(rows)} jug.)</span></summary>"
            + _table(["Jugador", "Pos", "Equipo", "Valor", "Pagó"], r) + "</details>"
        )
    squads = "".join(squads_html) or "<p class='muted'>Sin plantillas.</p>"

    # Pain
    pain_rows = [[_e(r["manager"]), f'{r["loss"]:.0f} €', str(r["resets"])] for r in data["pain"]]
    pain = _table(["Manager", "Pérdidas €", "Re-fianzas"], pain_rows) if pain_rows \
        else "<p class='muted'>Sin jornadas jugadas todavía.</p>"

    return _PAGE.format(
        league=league, me=me, generated=_e(generated), date=_e(data.get("date") or "—"),
        alert=alert_html, economy=econ, team=team, market=market, chollos=chollos,
        squads=squads, pain=pain,
    )


_PAGE = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>⚽ Biwenger · {league}</title>
<style>
  :root {{ --bg:#0f1420; --card:#182031; --muted:#8b97ad; --fg:#e8edf6; --accent:#3ddc84;
           --line:#26314a; --sell:#3a1720; --me:#13324a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
          font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  header {{ padding:16px 16px 0; position:sticky; top:0; z-index:5;
            background:linear-gradient(180deg,#0f1420,#0f1420ee);
            border-bottom:1px solid var(--line); backdrop-filter:blur(6px); }}
  h1 {{ margin:0; font-size:20px; }}
  .sub {{ color:var(--muted); font-size:13px; margin:3px 0 10px; }}
  nav {{ display:flex; gap:6px; overflow-x:auto; -webkit-overflow-scrolling:touch; padding-bottom:8px; }}
  nav button {{ flex:0 0 auto; background:transparent; color:var(--muted); border:1px solid var(--line);
                border-radius:999px; padding:7px 13px; font-size:14px; cursor:pointer; }}
  nav button.active {{ background:var(--accent); color:#08130c; border-color:var(--accent); font-weight:700; }}
  main {{ padding:14px; max-width:1000px; margin:0 auto; }}
  section {{ display:none; background:var(--card); border:1px solid var(--line); border-radius:14px;
             padding:14px; }}
  section.active {{ display:block; }}
  h2 {{ font-size:16px; margin:0 0 10px; }}
  .alert {{ background:var(--sell); border:1px solid #7a2233; color:#ffd7de;
            padding:11px 13px; border-radius:12px; margin:0 14px 4px; font-weight:600; }}
  .tw {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; min-width:420px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
  th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.03em; }}
  tr.me td {{ background:var(--me); }}
  tr.sell td {{ background:var(--sell); }}
  b {{ color:var(--accent); }}
  .muted {{ color:var(--muted); }}
  details {{ border:1px solid var(--line); border-radius:10px; margin:8px 0; padding:4px 10px; }}
  summary {{ cursor:pointer; padding:6px 0; font-weight:600; }}
  footer {{ color:var(--muted); font-size:12px; text-align:center; padding:20px; }}
</style></head>
<body>
<header>
  <h1>⚽ Biwenger · {league}</h1>
  <div class="sub">Tú: <b>{me}</b> · datos del {date} · generado {generated}</div>
  <nav>
    <button class="active" data-tab="economia">💰 Economía</button>
    <button data-tab="equipo">👕 Mi equipo</button>
    <button data-tab="mercado">🛒 Mercado</button>
    <button data-tab="chollos">💎 Chollos</button>
    <button data-tab="plantillas">📋 Plantillas</button>
    <button data-tab="pain">😱 Pain</button>
  </nav>
</header>
{alert}
<main>
  <section id="economia" class="active"><h2>💰 Economía (saldo · valor · puja máxima)</h2>{economy}
    <div class="muted" style="margin-top:8px;font-size:12px">Puja máxima = saldo + 0,25 × valor de equipo. Estimación (tu saldo es exacto).</div>
  </section>
  <section id="equipo"><h2>👕 Tu equipo</h2>{team}
    <div class="muted" style="margin-top:8px;font-size:12px">"Esperado" = puntos/partido (esta temporada o la pasada).</div>
  </section>
  <section id="mercado"><h2>🛒 Mercado de hoy (banca)</h2>{market}
    <div class="muted" style="margin-top:8px;font-size:12px">Puja sugerida = mercado +15%, limitada por tu puja máxima.</div>
  </section>
  <section id="chollos"><h2>💎 Chollos (mejor relación puntos/precio)</h2>{chollos}</section>
  <section id="plantillas"><h2>📋 Plantillas de la liga</h2>{squads}</section>
  <section id="pain"><h2>😱 Pain tracker (dinero real €)</h2>{pain}
    <div class="muted" style="margin-top:8px;font-size:12px">Castigo por jornada: último 3€, penúltimo 2€, antepenúltimo 1€.</div>
  </section>
</main>
<footer>Biwenger Analyzer · actualizado automáticamente cada día</footer>
<script>
  document.querySelectorAll('nav button').forEach(function(b){{
    b.addEventListener('click', function(){{
      document.querySelectorAll('nav button').forEach(function(x){{x.classList.remove('active');}});
      document.querySelectorAll('main section').forEach(function(s){{s.classList.remove('active');}});
      b.classList.add('active');
      document.getElementById(b.dataset.tab).classList.add('active');
      window.scrollTo(0,0);
    }});
  }});
</script>
</body></html>"""
