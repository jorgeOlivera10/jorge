"""Pain tracker: contabilidad de dinero REAL (euros) según la normativa.

Calcula, jornada a jornada, quién quedó último / penúltimo / antepenúltimo y
acumula los castigos (3 € / 2 € / 1 €). Aplica la regla 15 (al acumular 30 €
en pérdidas, se vuelve a pagar la fianza). NO tiene que ver con el saldo in-game.

Fuente: los resultados de 'roundFinished' del tablón (posición y puntos por
jornada), que ya parsea ingest/board.py.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from biwenger.ingest.board import ParsedRoundResult
from biwenger.rules import LeagueRules


@dataclass
class PainEntry:
    round: int
    user_id: int
    user_name: str | None
    concept: str          # 'penalty' | 'deposit_reset'
    amount_eur: float     # coste (positivo = € que debe pagar)


@dataclass
class PainTotal:
    user_id: int
    user_name: str | None
    penalties_eur: float
    deposit_resets: int
    total_eur: float


def _rank_from_bottom(results_in_round: list[ParsedRoundResult]) -> list[tuple[ParsedRoundResult, int]]:
    """Ordena de peor a mejor y asigna rango desde abajo (1 = último)."""
    # Preferimos 'position' (autoritativa); si falta, ordenamos por puntos asc.
    have_positions = all(r.position is not None for r in results_in_round)
    if have_positions:
        ordered = sorted(results_in_round, key=lambda r: -(r.position or 0))
    else:
        ordered = sorted(results_in_round, key=lambda r: (r.points if r.points is not None else 0))
    return [(r, i + 1) for i, r in enumerate(ordered)]


def compute_pain_ledger(
    round_results: list[ParsedRoundResult],
    rules: LeagueRules,
) -> list[PainEntry]:
    """Genera las entradas de castigo (y resets de fianza) por jornada."""
    by_round: dict[int, list[ParsedRoundResult]] = defaultdict(list)
    for r in round_results:
        if r.round is not None:
            by_round[r.round].append(r)

    rm = rules.real_money
    cumulative: dict[int, float] = defaultdict(float)
    entries: list[PainEntry] = []

    for rnd in sorted(by_round):
        ranked = _rank_from_bottom(by_round[rnd])
        for res, rank in ranked:
            penalty = rm.penalty_for_rank_from_bottom(rank)
            if penalty <= 0:
                continue
            entries.append(
                PainEntry(
                    round=rnd,
                    user_id=res.user_id,
                    user_name=res.user_name,
                    concept="penalty",
                    amount_eur=penalty,
                )
            )
            cumulative[res.user_id] += penalty
            # Regla 15: al llegar al umbral acumulado, se vuelve a pagar la fianza.
            if cumulative[res.user_id] >= rm.deposit_reset_threshold_eur:
                entries.append(
                    PainEntry(
                        round=rnd,
                        user_id=res.user_id,
                        user_name=res.user_name,
                        concept="deposit_reset",
                        amount_eur=rm.deposit_eur,
                    )
                )
                cumulative[res.user_id] -= rm.deposit_reset_threshold_eur

    return entries


def summarize_pain(entries: list[PainEntry]) -> list[PainTotal]:
    """Agrega las entradas por manager, ordenado por total descendente."""
    pen: dict[int, float] = defaultdict(float)
    resets: dict[int, int] = defaultdict(int)
    names: dict[int, str | None] = {}
    for e in entries:
        names[e.user_id] = e.user_name or names.get(e.user_id)
        if e.concept == "penalty":
            pen[e.user_id] += e.amount_eur
        elif e.concept == "deposit_reset":
            resets[e.user_id] += 1

    # total_eur = pérdidas acumuladas por castigos (dinero que debe). Los
    # deposit_resets se reportan aparte: nº de veces que tendría que re-pagar la
    # fianza (regla 15), no se suman al total para no contarlos dos veces.
    totals = [
        PainTotal(
            user_id=uid,
            user_name=names.get(uid),
            penalties_eur=pen[uid],
            deposit_resets=resets[uid],
            total_eur=pen[uid],
        )
        for uid in set(pen) | set(resets)
    ]
    totals.sort(key=lambda t: t.penalties_eur, reverse=True)
    return totals
