"""Carga de config/llm.json, plantillas_llm.json y mensajes_fijos.json (los textos y límites no van en el código)."""
import json
from functools import lru_cache
from pathlib import Path

from app.core.reglas import RUTA_REGLAS

RUTA_CONFIG: Path = RUTA_REGLAS.parent


def _leer(nombre: str) -> dict:
    return json.loads((RUTA_CONFIG / nombre).read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def cargar_llm() -> dict:
    return _leer("llm.json")


@lru_cache(maxsize=1)
def cargar_plantillas() -> dict:
    return _leer("plantillas_llm.json")


@lru_cache(maxsize=1)
def cargar_mensajes_fijos() -> dict:
    return _leer("mensajes_fijos.json")
