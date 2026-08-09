"""Motor y sesión de la base de datos (SQLite por defecto)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from biwenger.config import Settings, get_settings
from biwenger.db.models import Base


def make_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    url = settings.resolved_database_url()
    # check_same_thread=False para permitir uso desde el job/CLI sin sorpresas.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


def init_db(engine: Engine | None = None, settings: Settings | None = None) -> Engine:
    """Crea el esquema si no existe. Devuelve el engine."""
    engine = engine or make_engine(settings)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    engine = engine or make_engine()
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Context manager transaccional: commit al salir, rollback si hay error."""
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
