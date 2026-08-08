"""Configuración central de la aplicación.

Todos los valores se cargan desde variables de entorno / fichero .env mediante
pydantic-settings. NADA de credenciales ni IDs hardcodeados en el código.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del proyecto (carpeta biwenger/), calculada desde este fichero:
# src/biwenger/config.py -> parents[2] == biwenger/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Ajustes de la aplicación leídos desde el entorno o .env."""

    model_config = SettingsConfigDict(
        env_prefix="BIWENGER_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Credenciales de login ---
    email: str = Field(default="", description="Email de Biwenger (login).")
    password: str = Field(default="", description="Password de Biwenger (login).")

    # --- Cabeceras capturadas del navegador ---
    user_id: str = Field(default="", description="Cabecera X-User.")
    league_id: str = Field(default="", description="Cabecera X-League.")
    version: str = Field(default="", description="Cabecera X-Version.")

    league_name: str = Field(default="Mi Liga")

    # --- Sistemas de puntuación (parámetro ?score=) ---
    score_sofascore: int = Field(default=1, description="ID score de Sofascore (verificar).")
    score_as: int = Field(default=5, description="ID score de Picas del AS (scoreID de la liga).")
    score_default: str = Field(default="as", description="'sofascore' o 'as' (la liga usa AS=5).")

    # --- Economía ---
    initial_budget: int = Field(default=40_000_000, description="Presupuesto inicial por manager.")
    bid_team_value_factor: float = Field(
        default=0.25, description="Coeficiente del valor de equipo en la puja máxima."
    )

    # --- Persistencia ---
    # Nota: pydantic-settings mapea DATABASE_URL (sin prefijo) por el alias de abajo.
    database_url: str = Field(
        default="sqlite:///data/biwenger.db",
        validation_alias="DATABASE_URL",
    )

    # --- Red / rate limit ---
    min_request_interval: float = Field(default=1.0, description="Segundos mínimos entre peticiones.")
    cache_ttl: int = Field(default=3600, description="TTL de la caché en disco (segundos).")
    max_retries: int = Field(default=4, description="Reintentos ante errores de red/5xx.")

    # --- Logging ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def scores(self) -> dict[str, int]:
        """Mapa nombre -> id de score para los sistemas de puntuación activos."""
        return {"sofascore": self.score_sofascore, "as": self.score_as}

    def score_id(self, name: str | None = None) -> int:
        """Devuelve el id numérico de score para un nombre ('sofascore'/'as')."""
        key = (name or self.score_default).lower()
        try:
            return self.scores[key]
        except KeyError as exc:  # pragma: no cover - error de configuración
            raise ValueError(
                f"Sistema de puntuación desconocido: {key!r}. Usa uno de {list(self.scores)}."
            ) from exc

    def resolved_database_url(self) -> str:
        """URL de la BD con rutas SQLite relativas resueltas contra PROJECT_ROOT."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix):]
            path = Path(raw)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path}"
        return self.database_url


def get_settings() -> Settings:
    """Punto de acceso único a la configuración."""
    return Settings()
