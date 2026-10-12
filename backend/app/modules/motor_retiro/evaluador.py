"""Evaluador de reglas. Respeta el orden de reglas.json (orden_evaluacion_cierre: R6 → R8 → R7 → R5 → R2 → R1 → R4);
de esas, hoy solo existen R5, R1 y R4. La primera que corresponde detiene las siguientes."""
from dataclasses import dataclass

from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.niveles import NS_MAXIMO, NS_MINIMO
from app.modules.motor_retiro.reglas.base import Regla
from app.modules.motor_retiro.reglas.r1_retiro_estandar import R1RetiroEstandar
from app.modules.motor_retiro.reglas.r4_mantener import R4Mantener
from app.modules.motor_retiro.reglas.r5_refuerzo import R5Refuerzo

REGLAS_DISPONIBLES: dict[str, Regla] = {r.codigo: r for r in (R5Refuerzo(), R1RetiroEstandar(), R4Mantener())}


@dataclass(frozen=True)
class Evaluacion:
    regla: str
    ns_nuevo: int
    motivo: str
    clave_mensaje: str | None = None


def ordenar_reglas(orden: list[str], disponibles: dict[str, Regla] | None = None) -> list[Regla]:
    disponibles = REGLAS_DISPONIBLES if disponibles is None else disponibles
    reglas = [disponibles[c] for c in orden if c in disponibles]
    if "R4" in disponibles and all(r.codigo != "R4" for r in reglas):
        reglas.append(disponibles["R4"])  # R4 siempre cierra la secuencia
    return reglas


def evaluar(ctx: ContextoRegla, disponibles: dict[str, Regla] | None = None) -> Evaluacion:
    for regla in ordenar_reglas(ctx.config["orden_evaluacion_cierre"], disponibles):
        if regla.aplica(ctx):
            res = regla.ejecutar(ctx)
            ns = max(NS_MINIMO, min(NS_MAXIMO, int(res.ns_nuevo)))
            return Evaluacion(regla.codigo, ns, res.motivo, regla.clave_mensaje)
    return Evaluacion("R4", ctx.ns_actual, "ninguna regla corresponde: se mantiene")
