"""Exporta a CSV los datos seudonimizados para el análisis de la tesis (los mismos que GET /reportes/exportar).

Uso (desde la raíz del proyecto):
    python scripts/exportar_tesis.py                          # los cuatro CSV en ./exportacion_tesis
    python scripts/exportar_tesis.py --desde 2026-10-01 --hasta 2026-11-30 --salida mis_datos
    python scripts/exportar_tesis.py --tipo intentos          # un solo CSV (intentos, ayudas, cambios_ns, indicadores)

Los CSV no llevan nombres, correos ni el código SQL de los estudiantes: solo `id_pseudonimo`. Define ANON_SALT en el
.env ANTES de exportar; sin ella los seudónimos cambian en cada ejecución y los CSV de distintos días no se pueden unir.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal, cargar_modelos  # noqa: E402
from app.core.errores import ErrorApp  # noqa: E402
from app.modules.analitica import exportacion  # noqa: E402
from app.modules.progreso.fechas import interpretar_rango  # noqa: E402

AVISO_SAL = (
    "AVISO: ANON_SALT está vacía. Se usó una sal temporal: los seudónimos de esta exportación NO coincidirán con los de "
    "otra ejecución ni con los del servidor. Define ANON_SALT en el .env (python -c \"import secrets; print(secrets.token_hex(32))\") "
    "y vuelve a exportar si vas a comparar o unir datos de distintos días."
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exporta CSV seudonimizados para el análisis de la tesis.")
    ap.add_argument("--desde", help="AAAA-MM-DD (opcional)")
    ap.add_argument("--hasta", help="AAAA-MM-DD (opcional)")
    ap.add_argument("--tipo", choices=[*exportacion.TIPOS, "todos"], default="todos")
    ap.add_argument("--salida", default="exportacion_tesis", help="carpeta de destino (se crea si no existe)")
    args = ap.parse_args(argv)

    try:
        desde, hasta = interpretar_rango(args.desde, args.hasta)
    except ErrorApp as e:
        print(f"Error: {e.mensaje}", file=sys.stderr)
        return 2

    cargar_modelos()
    carpeta = Path(args.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    tipos = exportacion.TIPOS if args.tipo == "todos" else (args.tipo,)
    with SessionLocal() as db:
        for tipo in tipos:
            df = exportacion.tabla(db, tipo, desde, hasta)
            destino = carpeta / exportacion.nombre_archivo(tipo, desde, hasta)
            destino.write_text(exportacion.a_csv(df), encoding="utf-8", newline="")
            print(f"{destino}  ({len(df)} filas)")
    if not settings.anon_salt.strip():
        print(AVISO_SAL, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
