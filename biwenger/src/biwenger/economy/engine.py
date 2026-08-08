"""Motor económico: reconstrucción del saldo y la puja máxima de cada manager.

⚠️  TODO lo que produce este módulo es una ESTIMACIÓN. Se reconstruye a partir
    del tablón de movimientos, con estos supuestos y fuentes de error conocidas:
      - Presupuesto inicial igual para todos (config BIWENGER_INITIAL_BUDGET).
      - Valor de la plantilla INICIAL: si no se aporta, se asume 0 (managers que
        empezaron sin plantilla comprada). Si tu liga arrancó con draft, pásalo.
      - CESIONES y RETOS: se tratan como transferencias de dinero entre managers
        (quien cede/gana cobra; quien recibe/paga, paga). La API puede exponerlos
        con un 'type' propio; por eso se marcan como estimación (ver 'flags').
      - No se modelan cláusulas ni salarios (esta liga no los usa por defecto).

Fórmula (confirmada con proyectos reales y tu normativa):
    cash    = presupuesto_inicial − coste_plantilla_inicial
              + entradas(ventas, primas, cesiones cobradas)
              − salidas(fichajes, cesiones pagadas)
    max_bid = cash + factor * valor_de_equipo          (factor = 0.25)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from biwenger.ingest.board import ParsedMovement, ParsedRoundResult


@dataclass
class ManagerEconomy:
    user_id: int
    name: str | None
    initial_budget: int
    starting_squad_cost: int
    money_in: int          # ventas + cesiones cobradas
    money_out: int         # fichajes + cesiones pagadas
    awards: int            # primas (roundFinished bonus)
    cash: int              # saldo estimado
    team_value: int
    max_bid: int
    flags: list[str] = field(default_factory=list)  # avisos (p. ej. cesiones incluidas)


def _collect_user_ids(
    movements: list[ParsedMovement],
    round_results: list[ParsedRoundResult],
    team_values: dict[int, int],
) -> set[int]:
    ids: set[int] = set(team_values)
    for m in movements:
        if m.from_user_id is not None:
            ids.add(m.from_user_id)
        if m.to_user_id is not None:
            ids.add(m.to_user_id)
    for r in round_results:
        ids.add(r.user_id)
    return ids


def reconstruct(
    movements: list[ParsedMovement],
    round_results: list[ParsedRoundResult],
    team_values: dict[int, int],
    *,
    initial_budget: int,
    factor: float = 0.25,
    user_names: dict[int, str] | None = None,
    starting_squad_cost: dict[int, int] | None = None,
    include_unknown_types: bool = True,
) -> list[ManagerEconomy]:
    """Reconstruye la economía de todos los managers a partir del tablón.

    - team_values: {user_id: valor_de_equipo actual} (de standings).
    - include_unknown_types: si True, incluye cesiones/retos (tipos no estándar)
      en el saldo y añade un flag de aviso a los managers afectados.
    """
    user_names = user_names or {}
    starting_squad_cost = starting_squad_cost or {}

    ids = _collect_user_ids(movements, round_results, team_values)
    money_in = {uid: 0 for uid in ids}
    money_out = {uid: 0 for uid in ids}
    awards = {uid: 0 for uid in ids}
    unknown_involved: set[int] = set()

    for m in movements:
        is_unknown = m.note is not None
        if is_unknown and not include_unknown_types:
            continue
        amount = m.amount or 0
        if m.from_user_id is not None:
            money_in[m.from_user_id] = money_in.get(m.from_user_id, 0) + amount
            if is_unknown:
                unknown_involved.add(m.from_user_id)
        if m.to_user_id is not None:
            money_out[m.to_user_id] = money_out.get(m.to_user_id, 0) + amount
            if is_unknown:
                unknown_involved.add(m.to_user_id)

    for r in round_results:
        if r.bonus:
            awards[r.user_id] = awards.get(r.user_id, 0) + r.bonus

    result: list[ManagerEconomy] = []
    for uid in ids:
        start_cost = starting_squad_cost.get(uid, 0)
        m_in = money_in.get(uid, 0)
        m_out = money_out.get(uid, 0)
        aw = awards.get(uid, 0)
        cash = initial_budget - start_cost + m_in + aw - m_out
        tv = team_values.get(uid, 0)
        max_bid = int(cash + factor * tv)

        flags: list[str] = []
        if uid in unknown_involved:
            flags.append("incluye cesiones/retos (tipo no estándar): estimación menos fiable")
        if uid not in team_values:
            flags.append("sin valor de equipo (no aparece en standings)")

        result.append(
            ManagerEconomy(
                user_id=uid,
                name=user_names.get(uid),
                initial_budget=initial_budget,
                starting_squad_cost=start_cost,
                money_in=m_in,
                money_out=m_out,
                awards=aw,
                cash=cash,
                team_value=tv,
                max_bid=max_bid,
                flags=flags,
            )
        )

    result.sort(key=lambda e: e.cash + e.team_value, reverse=True)
    return result
