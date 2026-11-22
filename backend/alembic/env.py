"""Entorno de Alembic: usa la configuración y los modelos de la app (no duplica la URL de la BD)."""
from logging.config import fileConfig

from alembic import context

from app.core.db import Base, UTCDateTime, cargar_modelos, engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

cargar_modelos()  # registra todos los modelos en Base.metadata
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """La migración no debe depender del código de la app: UTCDateTime se escribe como DateTime(timezone=True)."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _opciones(dialecto: str) -> dict:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "render_item": render_item,
        "render_as_batch": dialecto == "sqlite",  # SQLite no soporta ALTER completo
    }


def run_migrations_offline() -> None:
    url = engine.url.render_as_string(hide_password=False)
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_opciones(engine.dialect.name))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Las pruebas pasan su propia conexión (config.attributes["connection"]); si no, se usa el engine de la app.
    conexion = config.attributes.get("connection")
    if conexion is not None:
        context.configure(connection=conexion, **_opciones(conexion.dialect.name))
        with context.begin_transaction():
            context.run_migrations()
        return
    with engine.connect() as connection:
        context.configure(connection=connection, **_opciones(connection.dialect.name))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
