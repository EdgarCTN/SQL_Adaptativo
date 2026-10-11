"""Borra la BD de desarrollo, recrea las tablas y siembra los datos iniciales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, SessionLocal, cargar_modelos, engine, init_db  # noqa: E402
from app.seeds.seed import sembrar_todo  # noqa: E402


def main() -> int:
    url = make_url(settings.database_url)
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
