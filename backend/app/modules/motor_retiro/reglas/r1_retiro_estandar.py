from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla, redondear


class R1RetiroEstandar(Regla):
    """R1 Retiro estándar (Matriz, Tabla 9).

    Condición: NS ≥ 1, ≥ 3 desafíos desde el último cambio y, en la ventana, TA ≥ 0.80, NI ≤ 2 y TR ≤ 1.25
    (las tres a la vez). Acción: el NS baja 1.
    Umbrales (reglas.json): ventana.minimo_desafios_desde_cambio, retiro_refuerzo.ta_retiro_min, ni_retiro_max,
    tr_retiro_estandar_max.
    Si ningún desafío de la ventana tiene tiempo medido, TR no se puede evaluar y NO se retira.
    Con `ctx.pausa_retiros > 0` (R3 o R12) no se retira.
    R11 (entrega 8): con la bandera inicial de sobreconfianza se exigen además los últimos
    r11_sobreconfianza.desafios_sa_exigidos_para_retiro desafíos en SA. Se comprueba aquí, como una pausa más, para
    que R13 (preferencia 3.4) nunca llegue a ver un retiro que R11 no permite.
    """

    codigo = "R1"
    clave_mensaje = "retiro_automatico"

    def aplica(self, ctx: ContextoRegla) -> bool:
        if ctx.pausa_retiros > 0:  # pausa tras recaída (R3) o cambio de dificultad (R12)
            return False
        if ctx.ns_actual < 1 or ctx.desafios_desde_cambio < ctx.config["ventana"]["minimo_desafios_desde_cambio"]:
            return False
        if not self.cumple_criterio_estandar(ctx):
            return False
        return not self.r11_bloquea(ctx)

    @staticmethod
    def cumple_criterio_estandar(ctx: ContextoRegla) -> bool:
        """TA, NI y TR del retiro estándar (sin pausa, sin R11)."""
        ind, rr = ctx.indicadores, ctx.config["retiro_refuerzo"]
        if ind.ta is None or ind.ni is None or ind.tr is None:
            return False
        return (
            redondear(ind.ta) >= rr["ta_retiro_min"]
            and redondear(ind.ni) <= rr["ni_retiro_max"]
            and redondear(ind.tr) <= rr["tr_retiro_estandar_max"]
        )

    @staticmethod
    def r11_bloquea(ctx: ContextoRegla) -> bool:
        """R11: con sobreconfianza, los últimos N desafíos de la ventana deben ser SA."""
        if not ctx.sobreconfianza:
            return False
        n = int(ctx.config["r11_sobreconfianza"]["desafios_sa_exigidos_para_retiro"])
        ultimos = ctx.cierres_recientes[-n:]
        return len(ultimos) < n or any(c.resultado != "SA" for c in ultimos)

    @classmethod
    def bloqueada_por_r11(cls, ctx: ContextoRegla) -> bool:
        """R1 se habría aplicado de no ser por R11 (el motor lo deja en eventos_motor)."""
        if ctx.pausa_retiros > 0 or ctx.ns_actual < 1:
            return False
        if ctx.desafios_desde_cambio < ctx.config["ventana"]["minimo_desafios_desde_cambio"]:
            return False
        return cls.cumple_criterio_estandar(ctx) and cls.r11_bloquea(ctx)

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        ind = ctx.indicadores
        return ResultadoRegla(
            ctx.ns_actual - 1,
            f"R1 retiro estándar: TA={ind.ta:.2f}, NI={ind.ni:g}, TR={ind.tr:.2f} en {ind.n} desafíos de la ventana",
        )
