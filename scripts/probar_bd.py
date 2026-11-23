"""Comprueba de punta a punta que la base de datos a la que apunta la app funciona.

Qué verifica (en este orden):
  1. A QUÉ base apunta (motor, host, base, de dónde sale la URL) y avisa si es SQLite, un host «-pooler» de Neon, etc.
  2. Que se puede conectar y la versión del servidor (PostgreSQL 18 recomendado).
  3. Que la BD está en la última revisión de Alembic.
  4. Que las tablas y columnas de los modelos existen en la BD.
  5. Que hay datos iniciales (conceptos, desafíos, cuestionario, usuario demo).
  6. Que se puede ESCRIBIR (inserta una fila y la deshace con rollback: no deja nada).

Es de solo lectura salvo el punto 6, que siempre se revierte (se omite con --sin-escritura).

Uso (desde la raíz del proyecto, con el entorno virtual activo):
  python scripts/probar_bd.py                 # usa la DATABASE_URL del .env
  python scripts/probar_bd.py --sin-escritura
  DATABASE_URL='postgresql://...neon.tech/...?sslmode=require' python scripts/probar_bd.py   # contra Neon, sin tocar .env

Código de salida: 0 = todo bien (los AVISO no fallan), 1 = hay al menos un FALLO.
"""
import argparse
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

for _flujo in (sys.stdout, sys.stderr):  # evita errores de codificación en consolas de Windows
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

fallos: list[str] = []
avisos: list[str] = []


def ok(msg: str) -> None:
    print(f"  [OK]    {msg}")


def aviso(msg: str) -> None:
    avisos.append(msg)
    print(f"  [AVISO] {msg}")


def fallo(msg: str) -> None:
    fallos.append(msg)
    print(f"  [FALLO] {msg}")


def titulo(texto: str) -> None:
    print(f"\n{texto}")


def origen_de_la_url() -> str:
    """Dice de dónde sale DATABASE_URL (variable de entorno, .env o el valor por defecto de SQLite)."""
    if os.environ.get("DATABASE_URL", "").strip():
        return "variable de entorno DATABASE_URL de esta sesión"
    env = RAIZ / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if linea.strip().startswith("DATABASE_URL=") and linea.split("=", 1)[1].strip():
                return f"archivo {env.name} de la raíz"
    return "valor por defecto de la app (SQLite)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Comprueba que la base de datos de la app funciona.")
    ap.add_argument("--sin-escritura", action="store_true", help="omite la prueba de escritura (insert + rollback)")
    args = ap.parse_args()

    try:
        from sqlalchemy import func, inspect, select, text
        from sqlalchemy.orm import Session

        from app.core.config import settings
        from app.core.db import Base, cargar_modelos, engine
    except Exception as e:  # dependencias sin instalar, .env inválido, etc.
        print(f"No se pudo cargar la app: {type(e).__name__}: {e}")
        print("Activa el entorno virtual (source backend/.venv/Scripts/activate) e instala: pip install -r backend/requirements-dev.txt")
        return 1

    cargar_modelos()
    url = engine.url
    es_sqlite = url.drivername.startswith("sqlite")
    host = (url.host or "").lower()

    # ------------------------------------------------------------------ 1. A qué base apunta
    titulo("1. Base de datos a la que apunta la app")
    print(f"  URL:     {url.render_as_string(hide_password=True)}")
    print(f"  Origen:  {origen_de_la_url()}")
    print(f"  Entorno: {settings.entorno}")
    if es_sqlite:
        aviso("Estás probando SQLite, NO PostgreSQL. Para PostgreSQL local: bash scripts/bd.sh probar  (o cambia DATABASE_URL en .env).")
    else:
        ok(f"Motor: PostgreSQL (host {url.host or '?'}, base {url.database})")
        if "-pooler" in host:
            aviso("El host es el «-pooler» de Neon. Para migrar (alembic) y respaldar usa la cadena DIRECTA (sin -pooler).")
        if host.endswith("neon.tech") and "sslmode" not in url.query:
            aviso("La URL de Neon no trae ?sslmode=require. Añádelo al final de la cadena.")

    # ------------------------------------------------------------------ 2. Conexión y versión
    titulo("2. Conexión y versión del servidor")
    try:
        t0 = time.perf_counter()
        with engine.connect() as conn:
            if es_sqlite:
                version = f"SQLite {conn.execute(text('select sqlite_version()')).scalar()}"
            else:
                version = conn.execute(text("select version()")).scalar() or ""
                num = int(conn.execute(text("show server_version_num")).scalar() or 0)
                mayor = num // 10000
        ms = (time.perf_counter() - t0) * 1000
        ok(f"Conexión correcta ({ms:.0f} ms): {version}")
        if not es_sqlite:
            if mayor >= 18:
                ok(f"PostgreSQL {mayor} (la versión recomendada para este proyecto es 18)")
            else:
                aviso(f"El servidor es PostgreSQL {mayor}. Funciona, pero el proyecto recomienda 18 (Neon, Docker y CI).")
    except Exception as e:
        fallo(f"No se pudo conectar: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
        if not es_sqlite:
            print("          Revisa: 1) ¿Docker Desktop está abierto y en ejecución? 2) ¿el contenedor está levantado? (bash scripts/bd.sh up)\n"
                  "          3) ¿usuario, clave, puerto y base correctos?")
        return resumen()

    # ------------------------------------------------------------------ 3. Revisión de Alembic
    titulo("3. Migraciones (Alembic)")
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        cfg = Config()
        cfg.set_main_option("script_location", str(RAIZ / "backend" / "alembic"))
        cabezas = ScriptDirectory.from_config(cfg).get_heads()
        with engine.connect() as conn:
            actual = MigrationContext.configure(conn).get_current_revision()
        if len(cabezas) != 1:
            fallo(f"Las migraciones tienen {len(cabezas)} cabezas (se esperaba 1).")
        elif actual == cabezas[0]:
            ok(f"La BD está en la última revisión ({actual})")
        elif actual is None:
            aviso("La BD no tiene revisión de Alembic. Si es nueva: cd backend && alembic upgrade head. "
                  "Si ya tenía tablas: alembic stamp head. (En desarrollo la app crea las tablas sola con create_all.)")
        else:
            fallo(f"La BD está en la revisión {actual!r} y la última es {cabezas[0]!r}. Ejecuta: cd backend && alembic upgrade head")
    except Exception as e:
        fallo(f"No se pudo leer la revisión de Alembic: {type(e).__name__}: {e}")

    # ------------------------------------------------------------------ 4. Tablas y columnas
    titulo("4. Esquema: tablas y columnas de los modelos")
    try:
        insp = inspect(engine)
        existentes = set(insp.get_table_names())
        faltan_tablas: list[str] = []
        faltan_columnas: list[str] = []
        for tabla in Base.metadata.sorted_tables:
            if tabla.name not in existentes:
                faltan_tablas.append(tabla.name)
                continue
            en_bd = {c["name"] for c in insp.get_columns(tabla.name)}
            for col in tabla.columns:
                if col.name not in en_bd:
                    faltan_columnas.append(f"{tabla.name}.{col.name}")
        total = len(Base.metadata.sorted_tables)
        if faltan_tablas:
            fallo(f"Faltan {len(faltan_tablas)} de {total} tablas: {', '.join(faltan_tablas)}")
        if faltan_columnas:
            fallo(f"Faltan columnas en tablas existentes: {', '.join(faltan_columnas)}")
        if not faltan_tablas and not faltan_columnas:
            ok(f"Las {total} tablas de los modelos existen con todas sus columnas")
    except Exception as e:
        fallo(f"No se pudo inspeccionar el esquema: {type(e).__name__}: {e}")

    # ------------------------------------------------------------------ 5. Datos iniciales
    titulo("5. Datos iniciales (seeds)")
    try:
        from app.modules.auth.models import Usuario
        from app.modules.desafios.models import Concepto, Desafio
        from app.modules.desafios.seeds import DESAFIOS
        from app.modules.linea_base.models import LineaBaseCuestionario
        from app.seeds.seed import CONCEPTOS

        with Session(engine) as db:
            n_conceptos = db.scalar(select(func.count()).select_from(Concepto)) or 0
            n_desafios = db.scalar(select(func.count()).select_from(Desafio)) or 0
            n_cuestionarios = db.scalar(
                select(func.count()).select_from(LineaBaseCuestionario).where(LineaBaseCuestionario.activo.is_(True))
            ) or 0
            n_usuarios = db.scalar(select(func.count()).select_from(Usuario)) or 0
            demo = None
            if settings.seed_usuario_demo:
                demo = db.scalar(select(Usuario.id).where(Usuario.correo == settings.demo_email.strip().lower()))
        esperado_c, esperado_d = len(CONCEPTOS), len(DESAFIOS)
        vacia = n_conceptos == 0 and n_desafios == 0
        if vacia:
            aviso("La base está vacía (sin datos iniciales). Se siembran al arrancar la app una vez, "
                  "o con: bash scripts/bd.sh sembrar")
        else:
            (ok if n_conceptos >= esperado_c else aviso)(f"Conceptos: {n_conceptos} (esperados {esperado_c})")
            (ok if n_desafios >= esperado_d else aviso)(f"Desafíos: {n_desafios} (esperados {esperado_d})")
            (ok if n_cuestionarios >= 1 else aviso)(f"Cuestionario de línea base activo: {n_cuestionarios}")
            if settings.seed_usuario_demo:
                (ok if demo else aviso)(f"Usuario demo ({settings.demo_email}): {'existe' if demo else 'no existe'}")
            print(f"          Usuarios en total: {n_usuarios}")
    except Exception as e:
        fallo(f"No se pudieron leer los datos iniciales: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")

    # ------------------------------------------------------------------ 6. Escritura (siempre se revierte)
    titulo("6. Escritura (insert + rollback; no deja nada)")
    if args.sin_escritura:
        print("  Omitida (--sin-escritura).")
    else:
        try:
            from app.modules.desafios.models import Concepto

            codigo = "__prueba_bd__"
            with Session(engine) as db:
                db.add(Concepto(codigo=codigo, nombre="Fila temporal de prueba"))
                db.flush()  # fuerza el INSERT real contra la BD
                leido = db.scalar(select(Concepto.id).where(Concepto.codigo == codigo))
                db.rollback()  # deshace todo
            with Session(engine) as db:
                quedo = db.scalar(select(Concepto.id).where(Concepto.codigo == codigo))
            if leido and not quedo:
                ok("Se pudo insertar, leer y revertir una fila (la BD acepta escrituras)")
            else:
                fallo("La prueba de escritura dio un resultado inesperado.")
        except Exception as e:
            fallo(f"No se pudo escribir en la BD: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")

    return resumen()


def resumen() -> int:
    print("\n" + "=" * 60)
    if fallos:
        print(f"RESULTADO: FALLÓ ({len(fallos)} fallo(s), {len(avisos)} aviso(s))")
        return 1
    print(f"RESULTADO: TODO BIEN ({len(avisos)} aviso(s))")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            from app.core.db import engine

            engine.dispose()
        except Exception:
            pass
