"""Motor económico: estima el saldo y la puja máxima de cada manager.

⚠️  Todo es una ESTIMACIÓN salvo mi propio saldo (que la API expone exacto).

Modelo (identidad de patrimonio neto):
    patrimonio = saldo + valor_de_equipo = presupuesto_inicial + primas + ganancias
Al inicio de la liga cada manager recibe `presupuesto_inicial` (40M) y una
plantilla aleatoria; su patrimonio de partida es 40M, así que:

    saldo ≈ presupuesto_inicial − valor_de_equipo + primas + flujos_de_cesiones

Fuentes de error conocidas: la apreciación/depreciación del valor de la plantilla
frente a su coste real, las ganancias/pérdidas realizadas en ventas (que no
modelamos con precisión sin el coste de compra del draft), salarios/cláusulas
(esta liga no los usa) y managers que guardan liquidez. Mi saldo es exacto
porque la API lo da; el de los rivales es estimado.

Puja máxima:
    puja_maxima = saldo + factor * valor_de_equipo        (factor = 0.25)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from biwenger.ingest.board import ParsedMovement, ParsedRoundResult

# Tipos de movimiento de compraventa (ya reflejados en el valor de equipo).
_TRANSFER_TYPES = {"transfer", "adminTransfer", "market"}


@dataclass
class ManagerEconomy:
    user_id: int
    name: str | None
    cash: int              # saldo estimado (o exacto para mí)
    team_value: int
    awards: int            # primas acumuladas (roundFinished)
    max_bid: int
    is_exact: bool = False
    flags: list[str] = field(default_factory=list)


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
    exact_cash: dict[int, int] | None = None,
    include_unknown_types: bool = True,
) -> list[ManagerEconomy]:
    """Estima la economía de todos los managers.

    - team_values: {user_id: valor_de_equipo} (de standings).
    - exact_cash: {user_id: saldo real} para managers cuyo balance conocemos (yo).
    - include_unknown_types: si True, suma/resta los flujos de cesiones/retos
      (movimientos de tipo no estándar) al saldo.
    """
    user_names = user_names or {}
    exact_cash = exact_cash or {}

    ids = _collect_user_ids(movements, round_results, team_values)

    # Primas (roundFinished bonus) por manager.
    awards: dict[int, int] = {uid: 0 for uid in ids}
    for r in round_results:
        if r.bonus:
            awards[r.user_id] = awards.get(r.user_id, 0) + r.bonus

    # Flujos especiales (cesiones/retos): tipos NO de compraventa. Estos mueven
    # dinero sin cambiar el valor de equipo, así que sí afectan al saldo.
    special: dict[int, int] = {uid: 0 for uid in ids}
    special_involved: set[int] = set()
    if include_unknown_types:
        for m in movements:
            if m.type in _TRANSFER_TYPES:
                continue
            amount = m.amount or 0
            if m.from_user_id is not None:
                special[m.from_user_id] = special.get(m.from_user_id, 0) + amount
                special_involved.add(m.from_user_id)
            if m.to_user_id is not None:
                special[m.to_user_id] = special.get(m.to_user_id, 0) - amount
                special_involved.add(m.to_user_id)

    result: list[ManagerEconomy] = []
    for uid in ids:
        tv = team_values.get(uid, 0)
        aw = awards.get(uid, 0)
        flags: list[str] = []

        if uid in exact_cash:
            cash = exact_cash[uid]
            is_exact = True
            flags.append("saldo EXACTO (de tu cuenta)")
        else:
            cash = initial_budget - tv + aw + special.get(uid, 0)
            is_exact = False
            if uid in special_involved:
                flags.append("incluye cesiones/retos")
            if uid not in team_values:
                flags.append("sin valor de equipo (no aparece en standings)")

        max_bid = int(cash + factor * tv)
        result.append(
            ManagerEconomy(
                user_id=uid,
                name=user_names.get(uid),
                cash=cash,
                team_value=tv,
                awards=aw,
                max_bid=max_bid,
                is_exact=is_exact,
                flags=flags,
            )
        )

    result.sort(key=lambda e: e.cash + e.team_value, reverse=True)
    return result
