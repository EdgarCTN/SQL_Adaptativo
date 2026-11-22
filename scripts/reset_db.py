"""Borra la BD de desarrollo, recrea las tablas y siembra los datos iniciales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, SessionLocal, cargar_modelos, engine, init_db  # noqa: E402
from app.seeds.seed import sembrar_todo  # noqa: E402


HOSTS_LOCALES = {"", "localhost", "127.0.0.1", "::1"}


def main() -> int:
    url = make_url(settings.database_url)
    # Guarda: este script BORRA todo. Nunca contra producción ni contra una BD remota (p. ej. Neon).
    if settings.es_produccion:
        print("RECHAZADO: ENTORNO=produccion. reset_db.py borra todos los datos y solo es para desarrollo local.")
        return 2
    if (url.host or "").lower() not in HOSTS_LOCALES:
        print(f"RECHAZADO: la BD está en un host no local ({url.host}). reset_db.py solo opera en SQLite o PostgreSQL local.")
        return 2
    cargar_modelos()
    engine.dispose()
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        archivo = Path(url.database)
        try:
            if archivo.exists():
                archivo.unlink()
                print(f"BD borrada: {archivo}")
        except PermissionError:
            print("No se pudo borrar la BD. Detén el servidor (uvicorn) y vuelve a intentarlo.")
            return 1
    else:
        Base.metadata.drop_all(bind=engine)
        print("Tablas eliminadas.")
    init_db()
    with SessionLocal() as db:
        sembrar_todo(db)
    print("Tablas recreadas y datos iniciales sembrados.")
    if settings.seed_usuario_demo:
        print(f"Usuario demo: {settings.demo_email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
