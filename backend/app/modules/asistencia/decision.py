"""Decisión del tipo de ayuda (función pura). Los mínimos y la primera ayuda por NS salen de reglas.json.

Fuera del MVP: banderas, ajuste +1 de los mínimos por dependencia (R9) y oferta automática.
"""
from dataclasses import dataclass

from app.core.reglas import cargar_reglas

ORDEN = ("AY1", "AY2", "AY3", "AY4")


@dataclass(frozen=True)
class DecisionAyuda:
    tipo: str | None  # None: ya vio AY4 y solo corresponde el recordatorio
    reformulada: bool = False  # repite el mismo tipo de la última ayuda (se le pide al LLM otra redacción)
    degradada: bool = False  # se bajó de tipo por no cumplir el mínimo de fallos
    ya_vio_ay4: bool = False


def _minimos(reglas: dict) -> dict[str, int]:
    cfg = reglas["ayuda_en_desafio"]
    return {"AY3": int(cfg["minimo_fallos_ay3"]), "AY4": int(cfg["minimo_fallos_ay4"])}


def primera_ayuda(ns: int, reglas: dict | None = None) -> str:
    reglas = reglas or cargar_reglas()
    return reglas["primera_ayuda_por_ns"][str(min(3, max(0, int(ns))))]


def _ajustar_por_minimos(tipo: str, fallos: int, minimos: dict[str, int]) -> str:
    """Si no se cumple el mínimo de fallos, se entrega el tipo inmediatamente inferior (y así hasta cumplirlo)."""
    while tipo in minimos and fallos < minimos[tipo] and ORDEN.index(tipo) > 0:
        tipo = ORDEN[ORDEN.index(tipo) - 1]
    return tipo


def decidir_ayuda(
    ns: int,
    fallos: int,
    ayudas_previas: list[str],
    fallos_desde_ultima_ayuda: int = 0,
    reglas: dict | None = None,
) -> DecisionAyuda:
    """
    ns: NS vigente del concepto. fallos: envíos fallidos del desafío. ayudas_previas: tipos entregados, en orden.
    fallos_desde_ultima_ayuda: envíos fallidos posteriores a la última ayuda entregada.
    """
    reglas = reglas or cargar_reglas()
    if "AY4" in ayudas_previas:
        return DecisionAyuda(None, ya_vio_ay4=True)
    minimos = _minimos(reglas)
    if not ayudas_previas:
        candidato = primera_ayuda(ns, reglas)
        if candidato == "AY4":  # AY4 nunca es la primera ayuda
            candidato = "AY3"
    else:
        ultima = ayudas_previas[-1]
        sube = fallos_desde_ultima_ayuda >= 1 and ultima != ORDEN[-1]
        candidato = ORDEN[ORDEN.index(ultima) + 1] if sube else ultima
    final = _ajustar_por_minimos(candidato, fallos, minimos)
    return DecisionAyuda(
        tipo=final,
        reformulada=bool(ayudas_previas) and final == ayudas_previas[-1],
        degradada=final != candidato,
    )
