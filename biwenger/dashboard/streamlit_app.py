"""Dashboard de Biwenger Analyzer (Streamlit).

Lee la base de datos que genera `biwenger daily` y muestra todo de un vistazo:
economía de rivales, tu equipo (estado/¿juega?/vender), alertas, chollos y el
Pain tracker. Pensado para verse bien también en el MÓVIL.

Ejecutar (en tu PC):
    pip install -e ".[dashboard]"
    streamlit run dashboard/streamlit_app.py

Para verlo en el móvil: con el móvil en el MISMO WiFi que el PC, abre la
"Network URL" que muestra Streamlit al arrancar (algo como http://192.168.x.x:8501).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select

from biwenger.analysis.expected import analyze_players
from biwenger.analysis.recommend import rank_chollos
from biwenger.analysis.scouting import player_outlook
from biwenger.config import get_settings
from biwenger.db import models
from biwenger.db.session import make_engine, session_scope

st.set_page_config(page_title="Biwenger Analyzer", page_icon="⚽", layout="wide")


def _money(n) -> str:
    try:
        return f"€{float(n):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _pos(position) -> str:
    return {1: "PT", 2: "DF", 3: "MC", 4: "DL"}.get(position or 0, "?")


@st.cache_data(ttl=60)
def load_data() -> dict:
    """Carga todo lo necesario desde la BD en estructuras simples (cacheado 60s)."""
    settings = get_settings()
    engine = make_engine(settings)
    out: dict = {"league": settings.league_name}
    with session_scope(engine) as s:
        users = {u.id: u for u in s.scalars(select(models.User)).all()}
        me = next((u for u in users.values() if u.is_me), None)
        out["me_name"] = me.name if me else None

        # Economía (último snapshot)
        last_econ = s.scalar(select(models.UserEconomy.date).order_by(models.UserEconomy.date.desc()))
        econ = []
        if last_econ is not None:
            for ue in s.scalars(select(models.UserEconomy).where(models.UserEconomy.date == last_econ)):
                u = users.get(ue.user_id)
                econ.append({
                    "Manager": (u.name if u else ue.user_id),
                    "Saldo": ue.cash, "Valor equipo": ue.team_value,
                    "Puja máxima": ue.max_bid, "Total": ue.cash + ue.team_value,
                })
        out["economy"] = sorted(econ, key=lambda r: r["Total"], reverse=True)
        out["econ_date"] = str(last_econ) if last_econ else None

        # Jugadores (para chollos)
        out["players"] = [_player_dict(p) for p in s.scalars(select(models.Player))]

        # Mi equipo (última plantilla)
        my_team = []
        if me is not None:
            last_sq = s.scalar(
                select(models.UserSquad.date).where(models.UserSquad.user_id == me.id)
                .order_by(models.UserSquad.date.desc())
            )
            if last_sq is not None:
                mine = s.scalars(
                    select(models.Player).join(
                        models.UserSquad, models.UserSquad.player_id == models.Player.id
                    ).where(models.UserSquad.user_id == me.id, models.UserSquad.date == last_sq)
                ).all()
                my_team = [_outlook_dict(player_outlook(p)) for p in mine]
        out["my_team"] = my_team

        # Plantillas de todos (última foto)
        last_sq_all = s.scalar(select(models.UserSquad.date).order_by(models.UserSquad.date.desc()))
        squads: dict[str, list] = {}
        if last_sq_all is not None:
            rows = s.execute(
                select(models.UserSquad, models.Player)
                .join(models.Player, models.Player.id == models.UserSquad.player_id, isouter=True)
                .where(models.UserSquad.date == last_sq_all)
            ).all()
            for sq, p in rows:
                name = users[sq.user_id].name if sq.user_id in users else str(sq.user_id)
                squads.setdefault(name, []).append({
                    "Jugador": (p.name if p else sq.player_id),
                    "Pos": _pos(p.position if p else None),
                    "Valor": (p.price if p else None),
                    "Pagó": sq.buy_price,
                })
        out["squads"] = squads

        # Pain tracker
        pain: dict[int, dict] = {}
        for led in s.scalars(select(models.RealMoneyLedger)):
            u = users.get(led.user_id)
            row = pain.setdefault(led.user_id, {"Manager": (u.name if u else led.user_id),
                                                "Pérdidas €": 0.0, "Re-fianzas": 0})
            if led.concept == "penalty":
                row["Pérdidas €"] += led.amount_eur
            elif led.concept == "deposit_reset":
                row["Re-fianzas"] += 1
        out["pain"] = sorted(pain.values(), key=lambda r: r["Pérdidas €"], reverse=True)

    return out


def _player_dict(p) -> dict:
    return {
        "id": p.id, "name": p.name, "position": p.position, "team_name": p.team_name,
        "price": p.price or 0, "price_increment": p.price_increment or 0,
        "total_points": p.total_points, "played": p.played,
        "points_home": p.points_home, "played_home": p.played_home,
        "points_away": p.points_away, "played_away": p.played_away,
        "status": p.status,
    }


def _outlook_dict(o) -> dict:
    return {
        "Jugador": o.name, "Pos": _pos(o.position), "Estado": o.status_label,
        "¿Juega?": o.will_play,
        "Esperado": o.expected_ppg if o.expected_ppg is not None else None,
        "Precio": o.price, "Tendencia": o.price_increment,
        "Vender": "🔴 VENDER" if o.sell_now else "", "Nota": o.note,
    }


# ------------------------------------------------------------------- UI
data = load_data()

st.title("⚽ Biwenger Analyzer")
st.caption(f"Liga: **{data['league']}**" + (f"  ·  Tú: **{data['me_name']}**" if data["me_name"] else ""))
if st.button("🔄 Recargar datos"):
    st.cache_data.clear()
    st.rerun()

if not data["economy"]:
    st.warning("No hay datos todavía. Ejecuta `biwenger daily` en el PC y recarga.")
    st.stop()

alerts = [r for r in data["my_team"] if r["Vender"]]
if alerts:
    st.error("🚨 A revisar: " + "  ·  ".join(f"{r['Jugador']} ({r['Estado']})" for r in alerts))

tabs = st.tabs(["💰 Economía", "👕 Mi equipo", "💎 Chollos", "🛒 Plantillas", "😱 Pain"])

with tabs[0]:
    st.subheader("Economía estimada por manager")
    st.caption(f"Snapshot: {data['econ_date']}  ·  Puja máxima = saldo + 0,25 × valor equipo (estimación)")
    df = pd.DataFrame(data["economy"])
    show = df.copy()
    for c in ("Saldo", "Valor equipo", "Puja máxima", "Total"):
        show[c] = show[c].map(_money)
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.bar_chart(df.set_index("Manager")["Puja máxima"])

with tabs[1]:
    st.subheader("Tu plantilla")
    if not data["my_team"]:
        st.info("Sin plantilla guardada. Ejecuta `biwenger daily`.")
    else:
        df = pd.DataFrame(data["my_team"])
        df["Precio"] = df["Precio"].map(_money)
        df["Tendencia"] = df["Tendencia"].map(
            lambda v: ("↑" if v > 0 else "↓" if v < 0 else "→") + (f" {abs(v):,.0f}" if v else "")
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Chollos — mejor relación puntos/precio")
    values = analyze_players(data["players"])
    max_price = st.slider("Precio máximo (M€)", 0, 60, 0, help="0 = sin límite") * 1_000_000
    chollos = rank_chollos(values, min_games=1, max_price=max_price or None, top=30)
    if not chollos:
        st.info("Aún no hay chollos con datos (¿temporada sin empezar?).")
    else:
        rows = [{"Jugador": c.name, "Pos": c.position_name, "Equipo": c.team_name,
                 "Precio": _money(c.price), "Pts/part.": c.points_per_match,
                 "Esperados": c.expected_points, "Valor (pts/M€)": c.value_ratio} for c in chollos]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Plantillas de la liga")
    squads = data["squads"]
    if not squads:
        st.info("Sin plantillas. Ejecuta `biwenger daily`.")
    else:
        who = st.selectbox("Manager", sorted(squads))
        rows = sorted(squads[who], key=lambda r: (r["Valor"] or 0), reverse=True)
        df = pd.DataFrame(rows)
        for c in ("Valor", "Pagó"):
            df[c] = df[c].map(_money)
        st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Pain tracker — dinero real (€)")
    if not data["pain"]:
        st.info("Sin jornadas jugadas todavía.")
    else:
        st.dataframe(pd.DataFrame(data["pain"]), use_container_width=True, hide_index=True)
        st.caption("Castigo por jornada: último 3€, penúltimo 2€, antepenúltimo 1€.")
