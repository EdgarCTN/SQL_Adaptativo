from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla, redondear


class R1RetiroEstandar(Regla):
    """R1 Retiro estándar (Matriz, Tabla 9).

    Condición: NS ≥ 1, ≥ 3 desafíos desde el último cambio y, en la ventana, TA ≥ 0.80, NI ≤ 2 y TR ≤ 1.25
    (las tres a la vez). Acción: el NS baja 1.
    Umbrales (reglas.json): ventana.minimo_desafios_desde_cambio, retiro_refuerzo.ta_retiro_min, ni_retiro_max,
    tr_retiro_estandar_max.
    Simplificaciones de esta versión mínima: TR usa fin − inicio como tiempo activo (provisional); si ningún
    desafío de la ventana tiene tiempo medido, TR no se puede evaluar y NO se retira. No se aplican aún R11
    (exigir 2 SA tras sobreconfianza), R3 (pausa tras recaída), R12 (pausa por cambio de dificultad) ni la
    preferencia 3.4 de R13: el retiro es siempre automático.
    """

    codigo = "R1"
    clave_mensaje = "retiro_automatico"

    def aplica(self, ctx: ContextoRegla) -> bool:
        ind, rr = ctx.indicadores, ctx.config["retiro_refuerzo"]
        if ctx.ns_actual < 1 or ctx.desafios_desde_cambio < ctx.config["ventana"]["minimo_desafios_desde_cambio"]:
            return False
        if ind.ta is None or ind.ni is None or ind.tr is None:
            return False
        return (
            redondear(ind.ta) >= rr["ta_retiro_min"]
            and redondear(ind.ni) <= rr["ni_retiro_max"]
            and redondear(ind.tr) <= rr["tr_retiro_estandar_max"]
        )

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        ind = ctx.indicadores
        return ResultadoRegla(
            ctx.ns_actual - 1,
            f"R1 retiro estándar: TA={ind.ta:.2f}, NI={ind.ni:g}, TR={ind.tr:.2f} en {ind.n} desafíos de la ventana",
        )
