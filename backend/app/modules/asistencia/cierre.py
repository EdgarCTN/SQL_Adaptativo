"""Clasificación del resultado de un desafío resuelto (Tabla 3): SA, CP, CE o NR."""
from app.core.reglas import cargar_reglas
from app.modules.asistencia.decision import ORDEN, primera_ayuda


def clasificar_cierre(tipos_recibidos: list[str], ns: int, reglas: dict | None = None) -> str:
    """SA: sin ayuda · CP: solo ayudas ≤ la primera del NS · CE: más que eso · NR: se entregó AY4."""
    reglas = reglas or cargar_reglas()
    if "AY4" in tipos_recibidos:
        return "NR"
    if not tipos_recibidos:
        return "SA"
    tope = ORDEN.index(primera_ayuda(ns, reglas))
    return "CP" if all(ORDEN.index(t) <= tope for t in tipos_recibidos) else "CE"
