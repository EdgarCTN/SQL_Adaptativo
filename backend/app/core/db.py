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
if _es_sqlite:
    _opciones_engine: dict = {"connect_args": {"check_same_thread": False}}
else:
    # PostgreSQL (Neon): pool pequeño; reciclar antes de que Neon suspenda el cómputo ocioso (5 min).
    # prepare_threshold=None desactiva los prepared statements de psycopg 3, que fallan tras PgBouncer (host "-pooler").
    _opciones_engine = {
        "connect_args": {"connect_timeout": 15, "prepare_threshold": None},
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": settings.db_pool_recycle,
        "pool_timeout": 30,
    }
engine = create_engine(settings.database_url, pool_pre_ping=True, **_opciones_engine)

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
    from app.modules.admin import models as _admin  # noqa: F401
    from app.modules.analitica import models as _analitica  # noqa: F401
    from app.modules.asistencia import models as _asistencia  # noqa: F401
    from app.modules.auth import models as _auth  # noqa: F401
    from app.modules.desafios import models as _desafios  # noqa: F401
    from app.modules.linea_base import models as _linea_base  # noqa: F401
    from app.modules.motor_retiro import models as _motor_retiro  # noqa: F401
    from app.modules.notificaciones import models as _notificaciones  # noqa: F401


def init_db() -> None:
    cargar_modelos()
    Base.metadata.create_all(bind=engine)


def verificar_esquema(bind=None) -> None:
    """Producción (sin create_all): exige que la BD esté en la última revisión de Alembic, o falla con un mensaje claro."""
    from pathlib import Path

    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    cabezas = ScriptDirectory.from_config(cfg).get_heads()
    if len(cabezas) != 1:
        raise RuntimeError(f"Migraciones de Alembic inválidas: se esperaba 1 cabeza y hay {len(cabezas)}. Genera la migración inicial (docs/MIGRACIONES.md).")
    with (bind or engine).connect() as conn:
        actual = MigrationContext.configure(conn).get_current_revision()
    if actual != cabezas[0]:
        raise RuntimeError(
            f"La BD está en la revisión {actual!r} y la app espera {cabezas[0]!r}. "
            "Ejecuta 'alembic upgrade head' (BD nueva) o 'alembic stamp head' (BD que ya tiene las tablas); ver docs/MIGRACIONES.md."
        )
