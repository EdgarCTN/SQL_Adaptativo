"""Base de datos: engine, sesión, Base declarativa y fecha UTC portable."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Guarda UTC y siempre devuelve datetimes con zona (SQLite pierde la zona)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


_es_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _es_sqlite else {},
    pool_pre_ping=True,
)

if _es_sqlite:

    @event.listens_for(engine, "connect")
    def _activar_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def cargar_modelos() -> None:
    """Importa todos los modelos para registrarlos en Base (las entregas siguientes añaden los suyos)."""
    from app.modules.asistencia import models as _asistencia  # noqa: F401
    from app.modules.auth import models as _auth  # noqa: F401
    from app.modules.desafios import models as _desafios  # noqa: F401
    from app.modules.linea_base import models as _linea_base  # noqa: F401


def init_db() -> None:
    cargar_modelos()
    Base.metadata.create_all(bind=engine)
