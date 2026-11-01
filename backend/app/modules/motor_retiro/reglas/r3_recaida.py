from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.indicadores import EXITOS
from app.modules.motor_retiro.reglas.base import ACCION_CAMBIAR_NS, Regla, ResultadoRegla


class R3Recaida(Regla):
    """R3 Recaída (Matriz, Tabla 9, bloque 2). No está en la secuencia de evaluación: el evaluador la mira antes.

    Condición: el último cambio de NS del concepto fue un retiro (R1 o R2; `ctx.ns_previo_retiro` solo viene con valor
    en ese caso) y los 2 desafíos siguientes (exactamente los 2 primeros desde el cambio) fueron CE o NR.
    Acción: el NS vuelve al valor anterior al retiro y R1 y R2 se pausan 3 desafíos (el motor guarda la pausa).
    Umbrales (reglas.json): recaida_y_pausas.desafios_ce_nr_para_recaida y desafios_sin_retiro_tras_recaida_o_cambio_dificultad.
    No se evalúa al omitir (las omisiones no cuentan como desafíos desde el cambio).
    """

    codigo = "R3"
    clave_mensaje = "recaida"

    def aplica(self, ctx: ContextoRegla) -> bool:
        if ctx.omision_motivo is not None or ctx.ns_previo_retiro is None or ctx.ns_previo_retiro <= ctx.ns_actual:
            return False
        n = int(ctx.config["recaida_y_pausas"]["desafios_ce_nr_para_recaida"])
        if ctx.desafios_desde_cambio != n or len(ctx.cierres_recientes) < n:
            return False
        return all(c.resultado not in EXITOS for c in ctx.cierres_recientes[-n:])

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        cfg = ctx.config["recaida_y_pausas"]
        n = int(cfg["desafios_ce_nr_para_recaida"])
        pausa = int(cfg["desafios_sin_retiro_tras_recaida_o_cambio_dificultad"])
        return ResultadoRegla(
            int(ctx.ns_previo_retiro),
            f"R3 recaída: los {n} desafíos siguientes al retiro fueron CE o NR; el NS vuelve de {ctx.ns_actual} a "
            f"{ctx.ns_previo_retiro} y R1 y R2 se pausan {pausa} desafíos",
            accion=ACCION_CAMBIAR_NS,
            pausa_retiros=pausa,
        )
