from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.niveles import NS_MAXIMO, NS_POR_DEFECTO
from app.modules.motor_retiro.reglas.base import ACCION_ESTANCAMIENTO, Regla, ResultadoRegla, redondear


class R6Estancamiento(Regla):
    """R6 Estancamiento (Matriz, Tabla 9, bloque 3). Solo con NS = 3; el NS no cambia.

    (a) TA < 0.50, ≥ 3 desafíos desde el último cambio y ya hubo un refuerzo previo en el concepto (el motor cuenta
    las filas de historial_niveles cuya regla está en r6_estancamiento.reglas_que_cuentan_como_refuerzo, PROVISIONAL).
    (b) 2 omisiones «Muy difícil» seguidas con el NS ya en 3 al llegar la segunda (al omitir no se mira la ventana).
    Acción: prerrequisito dominado (NS vigente ≤ ns_maximo_prerrequisito_dominado) o sin prerrequisito →
    `estancamiento_derivar`; si no → `estancamiento_previo_sin_dominar` (el motor añade el enlace a sus desafíos).
    Umbrales (reglas.json): retiro_refuerzo.ta_refuerzo_max (el mismo 0.50 de R5), ventana.minimo_desafios_desde_cambio,
    r6_estancamiento.*. Sin cambio de NS, la regla vuelve a corresponder en cada cierre mientras se siga cumpliendo.
    """

    codigo = "R6"
    aplica_en_omision = True

    def _condicion(self, ctx: ContextoRegla) -> str | None:
        if ctx.ns_actual < NS_MAXIMO:
            return None
        cfg = ctx.config["r6_estancamiento"]
        if ctx.omision_motivo is not None:  # (b)
            seguidas = int(cfg["omisiones_muy_dificil_seguidas"])
            return "b" if ctx.omision_motivo == "muy_dificil" and ctx.omisiones_muy_dificil_seguidas >= seguidas else None
        ind = ctx.indicadores  # (a)
        if ind.ta is None or ctx.desafios_desde_cambio < ctx.config["ventana"]["minimo_desafios_desde_cambio"]:
            return None
        if redondear(ind.ta) < ctx.config["retiro_refuerzo"]["ta_refuerzo_max"] and ctx.refuerzos_previos > 0:
            return "a"
        return None

    def aplica(self, ctx: ContextoRegla) -> bool:
        return self._condicion(ctx) is not None

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        condicion = self._condicion(ctx)
        tiene_previo = ctx.prerrequisito_codigo is not None
        ns_previo = ctx.prerrequisito_ns if ctx.prerrequisito_ns is not None else NS_POR_DEFECTO
        dominado = (not tiene_previo) or ns_previo <= int(ctx.config["r6_estancamiento"]["ns_maximo_prerrequisito_dominado"])
        if condicion == "a":
            ind = ctx.indicadores
            causa = (
                f"R6 estancamiento (a): NS 3, TA={ind.ta:.2f}, {ctx.desafios_desde_cambio} desafíos desde el último cambio "
                f"y {ctx.refuerzos_previos} refuerzo(s) previo(s)"
            )
        else:
            causa = f"R6 estancamiento (b): {ctx.omisiones_muy_dificil_seguidas} omisiones «Muy difícil» seguidas con NS 3"
        if not tiene_previo:
            destino = "sin prerrequisito: derivar"
        elif dominado:
            destino = f"prerrequisito «{ctx.prerrequisito_nombre}» dominado (NS {ns_previo}): derivar"
        else:
            destino = f"prerrequisito «{ctx.prerrequisito_nombre}» sin dominar (NS {ns_previo}): practicarlo"
        return ResultadoRegla(
            ctx.ns_actual,
            f"{causa}; {destino}",
            accion=ACCION_ESTANCAMIENTO,
            clave_mensaje="estancamiento_derivar" if dominado else "estancamiento_previo_sin_dominar",
            extra={
                "r6_condicion": condicion,
                "prerrequisito": ctx.prerrequisito_codigo,
                "prerrequisito_ns": ns_previo if tiene_previo else None,
            },
        )
