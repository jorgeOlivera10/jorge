"""Constantes de la normativa de la liga (Pain&Gain 26/27).

Estos valores NO son secretos y rara vez cambian, así que viven en código (no en
.env). El motor económico (Fase 4) y el Pain tracker (dinero real) los usan.
Documentación completa en docs/normativa.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RealMoneyRules:
    """Contabilidad en dinero REAL (euros), ajena al saldo de Biwenger."""

    deposit_eur: float = 30.0   # fianza
    entry_eur: float = 30.0     # entrada
    # Castigo por posición al final de cada jornada (último, penúltimo, antepenúltimo).
    last_place_eur: float = 3.0
    second_last_eur: float = 2.0
    third_last_eur: float = 1.0
    # Regla 15: al acumular esta cantidad en pérdidas, se vuelve a pagar la fianza.
    deposit_reset_threshold_eur: float = 30.0

    def penalty_for_rank_from_bottom(self, rank_from_bottom: int) -> float:
        """€ de castigo según puesto contando desde el último (1=último)."""
        return {1: self.last_place_eur, 2: self.second_last_eur, 3: self.third_last_eur}.get(
            rank_from_bottom, 0.0
        )


@dataclass(frozen=True)
class InGamePrizes:
    """Primas in-game por clasificación de jornada (regla 8), en € de Biwenger."""

    first: int = 1_000_000
    second: int = 500_000
    third: int = 250_000
    ideal_eleven_per_player: int = 500_000
    mvp: int = 750_000


@dataclass(frozen=True)
class LoanRules:
    """Reglas de cesiones (reglas 2, 6, 11, 14)."""

    min_amount: int = 200_000       # importe mínimo por cesión
    max_amount: int = 1_000_000     # precio máximo por cesión
    max_received_per_player_round: int = 2
    max_loans_per_round: int = 3


@dataclass(frozen=True)
class ChallengeRules:
    """Reglas de retos (regla 7)."""

    max_per_week: int = 2
    max_bet: int = 1_000_000


@dataclass(frozen=True)
class LeagueRules:
    """Agrupa toda la normativa relevante para los cálculos."""

    real_money: RealMoneyRules = field(default_factory=RealMoneyRules)
    prizes: InGamePrizes = field(default_factory=InGamePrizes)
    loans: LoanRules = field(default_factory=LoanRules)
    challenges: ChallengeRules = field(default_factory=ChallengeRules)
    # Regla 12: en las últimas N jornadas no hay cesiones ni compraventa entre usuarios.
    locked_final_rounds: int = 3
    # Regla 13: días mínimos para revender a un antiguo propietario.
    resell_to_previous_owner_days: int = 10


# Instancia por defecto usada por el resto del código.
LEAGUE_RULES = LeagueRules()
