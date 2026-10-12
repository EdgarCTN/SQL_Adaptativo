from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.niveles import NS_MAXIMO
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla, redondear


class R5Refuerzo(Regla):
    """R5 Refuerzo (Matriz, Tabla 9).

    Condición: ≥ 3 desafíos desde el último cambio de NS y (TA < 0.50, o NI ≥ 4 con TA < 0.80).
    Acción: el NS sube 1 (máximo 3).
    Umbrales (reglas.json): ventana.minimo_desafios_desde_cambio, retiro_refuerzo.ta_refuerzo_max,
    ni_refuerzo_min y ta_retiro_min (el «0.80» de la segunda condición es el mismo umbral que el de R1).
    Con NS = 3 la regla corresponde pero no hay a dónde subir: queda en 3 (R6 Estancamiento aún no está).
    Indicadores: TA y NI de la ventana (ver indicadores.py).
    """

    codigo = "R5"
    clave_mensaje = "refuerzo"

    def aplica(self, ctx: ContextoRegla) -> bool:
        ind, rr = ctx.indicadores, ctx.config["retiro_refuerzo"]
        if ctx.desafios_desde_cambio < ctx.config["ventana"]["minimo_desafios_desde_cambio"] or ind.ta is None:
            return False
        if redondear(ind.ta) < rr["ta_refuerzo_max"]:
            return True
        return ind.ni is not None and ind.ni >= rr["ni_refuerzo_min"] and redondear(ind.ta) < rr["ta_retiro_min"]

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        ind = ctx.indicadores
        detalle = f"TA={ind.ta:.2f}, NI={ind.ni:g} en {ind.n} desafíos de la ventana"
        if ctx.ns_actual >= NS_MAXIMO:
            return ResultadoRegla(ctx.ns_actual, f"R5 corresponde ({detalle}) pero el NS ya está en el máximo")
        return ResultadoRegla(ctx.ns_actual + 1, f"R5 refuerzo: {detalle}")
