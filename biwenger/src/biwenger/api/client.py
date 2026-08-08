"""Cliente HTTP para la API NO oficial de Biwenger.

Responsabilidades (todas las que quieres para no acabar baneado):
  - Login con email/password -> token Bearer.
  - Inyección de cabeceras (Authorization, X-User, X-League, X-Version, X-Lang).
  - Reintentos con backoff exponencial ante errores de red / 5xx (tenacity).
  - Throttling: intervalo mínimo garantizado entre peticiones.
  - Caché en disco de respuestas GET (TTL configurable) para reducir peticiones.

Las URLs concretas viven en `endpoints.py`; este módulo solo sabe *cómo* pedir,
no *qué* URL. Así, si la API cambia, se toca un único sitio.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from biwenger.api import endpoints
from biwenger.config import PROJECT_ROOT, Settings, get_settings
from biwenger.logging_setup import get_logger

log = get_logger(__name__)

# Errores de red que merecen reintento.
_RETRYABLE = (httpx.TransportError, httpx.RemoteProtocolError)


class BiwengerAPIError(RuntimeError):
    """Error de nivel de aplicación al hablar con la API de Biwenger."""


class _ServerError(Exception):
    """Interno: marca un 5xx para que tenacity reintente."""


class DiskCache:
    """Caché muy simple en disco (un JSON por URL) con expiración por TTL."""

    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.dir = directory
        self.ttl = ttl_seconds
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.dir / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        if self.ttl >= 0 and (time.time() - path.stat().st_mtime) > self.ttl:
            return None
        try:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any) -> None:
        try:
            with self._path(key).open("w", encoding="utf-8") as fh:
                json.dump(value, fh)
        except OSError as exc:  # pragma: no cover - problema de disco
            log.warning("No se pudo escribir en caché: %s", exc)


class BiwengerClient:
    """Cliente de alto nivel para la API de Biwenger.

    Uso típico:
        client = BiwengerClient(settings)
        client.login()                       # opcional para endpoints públicos
        data = client.get_competition_data("sofascore")
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        cache: DiskCache | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._token: str | None = None
        self._last_request_ts = 0.0
        self._lock = threading.Lock()

        self.cache = cache or DiskCache(
            PROJECT_ROOT / ".cache", self.settings.cache_ttl
        )
        # `transport` permite inyectar un MockTransport en los tests (sin red).
        self._http = httpx.Client(
            timeout=httpx.Timeout(30.0),
            transport=transport,
            follow_redirects=True,
        )

    # ---- ciclo de vida ------------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BiwengerClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- cabeceras ----------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if self.settings.user_id:
            h["X-User"] = self.settings.user_id
        if self.settings.league_id:
            h["X-League"] = self.settings.league_id
        if self.settings.version:
            h["X-Version"] = self.settings.version
        h["X-Lang"] = "en"
        return h

    # ---- throttling ---------------------------------------------------------
    def _throttle(self) -> None:
        """Garantiza un intervalo mínimo entre peticiones (anti rate-limit)."""
        with self._lock:
            elapsed = time.time() - self._last_request_ts
            wait = self.settings.min_request_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.time()

    # ---- peticiones de bajo nivel (con reintentos) --------------------------
    def _request(self, method: str, url: str, *, json_body: Any | None = None) -> httpx.Response:
        @retry(
            retry=retry_if_exception_type(_RETRYABLE + (_ServerError,)),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self.settings.max_retries),
            reraise=True,
        )
        def _do() -> httpx.Response:
            self._throttle()
            log.debug("%s %s", method, url)
            resp = self._http.request(method, url, headers=self._headers(), json=json_body)
            if resp.status_code >= 500:
                raise _ServerError(f"{resp.status_code} en {url}")
            return resp

        return _do()

    def get_json(self, url: str, *, use_cache: bool = True) -> Any:
        """GET que devuelve JSON, con caché en disco opcional."""
        if use_cache:
            cached = self.cache.get(url)
            if cached is not None:
                log.debug("cache HIT %s", url)
                return cached
        resp = self._request("GET", url)
        if resp.status_code == 401:
            raise BiwengerAPIError("401 No autorizado: revisa token y cabeceras (X-User/X-League).")
        if resp.status_code >= 400:
            raise BiwengerAPIError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
        data = resp.json()
        if use_cache:
            self.cache.set(url, data)
        return data

    # ---- autenticación ------------------------------------------------------
    def login(self) -> str:
        """Hace login y guarda el token Bearer. Devuelve el token."""
        if not self.settings.email or not self.settings.password:
            raise BiwengerAPIError(
                "Faltan credenciales: define BIWENGER_EMAIL y BIWENGER_PASSWORD en .env."
            )
        payload = {"email": self.settings.email, "password": self.settings.password}
        resp = self._request("POST", endpoints.login(), json_body=payload)
        if resp.status_code >= 400:
            raise BiwengerAPIError(f"Login falló: HTTP {resp.status_code} — {resp.text[:200]}")
        data = resp.json()
        token = data.get("token") or data.get("data", {}).get("token")
        if not token:
            raise BiwengerAPIError(f"Login sin token en la respuesta: {list(data)[:5]}")
        self._token = token
        log.info("Login correcto; token obtenido.")
        return token

    # ---- endpoints de alto nivel -------------------------------------------
    def get_competition_data(self, score_name: str | None = None) -> Any:
        """Datos de todos los jugadores para un sistema de puntuación."""
        score = self.settings.score_id(score_name)
        return self.get_json(endpoints.competition_data(score))

    def get_player_detail(self, alias: str, score_name: str | None = None) -> Any:
        score = self.settings.score_id(score_name)
        return self.get_json(endpoints.player_detail(alias, score))

    def get_market_daily(self) -> Any:
        return self.get_json(endpoints.market_daily(), use_cache=False)

    def get_league(self) -> Any:
        """Liga activa (según cabecera X-League): standings y managers."""
        return self.get_json(endpoints.league(), use_cache=False)

    def get_rounds_league(self) -> Any:
        """Clasificación por jornada (puntos de cada plantilla por ronda)."""
        return self.get_json(endpoints.rounds_league(), use_cache=False)

    def get_user_team(self, user_id: str) -> Any:
        """Equipo de un manager (players con owner.price, lineups, offers...)."""
        return self.get_json(endpoints.user_team(user_id), use_cache=False)

    def get_my_market(self) -> Any:
        """Mercado/ofertas del usuario autenticado."""
        return self.get_json(endpoints.my_market(), use_cache=False)

    def get_board(self, offset: int = 0, limit: int = 500) -> Any:
        """Una página del tablón de movimientos."""
        return self.get_json(
            endpoints.league_board(self.settings.league_id, offset, limit),
            use_cache=False,
        )

    def get_full_board(self, page_size: int = 500, max_pages: int = 20) -> list[Any]:
        """Tablón COMPLETO desde el inicio, paginando hasta agotar movimientos."""
        movements: list[Any] = []
        for page in range(max_pages):
            batch = self.get_board(offset=page * page_size, limit=page_size)
            if not batch:
                break
            movements.extend(batch)
            if len(batch) < page_size:
                break
        return movements
