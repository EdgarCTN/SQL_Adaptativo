"""Carga de backend/app/config/reglas.json (umbrales y valores de la Matriz; nunca van en el código)."""
import json
from functools import lru_cache
from pathlib import Path

RUTA_REGLAS = Path(__file__).resolve().parents[1] / "config" / "reglas.json"

_CLAVES_OBLIGATORIAS = ("valor_dominio_m", "cortes_linea_base", "r9_dependencia", "r11_sobreconfianza")


def leer_reglas(ruta: Path = RUTA_REGLAS) -> dict:
    """Lee y valida lo mínimo. Lanza OSError o ValueError si el archivo no sirve."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8-sig"))
    faltan = [k for k in _CLAVES_OBLIGATORIAS if k not in datos]
    if faltan:
        raise ValueError(f"reglas.json no tiene las claves: {', '.join(faltan)}")
    return datos


@lru_cache(maxsize=1)
def cargar_reglas() -> dict:
    """Se lee una vez por proceso; para recalibrar, edita reglas.json y reinicia el servidor."""
    return leer_reglas()
