from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.indicadores import calcular_indicadores
from app.modules.motor_retiro.niveles import NS_MINIMO
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla, redondear


class R2RetiroAcelerado(Regla):
    """R2 Retiro acelerado (Matriz, Tabla 9).

    Condición: NS ≥ 1 y los últimos 3 desafíos desde el último cambio fueron SA, con 1 intento cada uno y TR ≤ 1.0.
    Acción: el NS baja 2 (mínimo 0). Un desafío con ayuda mostrada sola no es SA, así que ya queda fuera por su resultado.
    Umbrales (reglas.json): retiro_refuerzo.desafios_limpios_acelerado, intentos_desafio_limpio, tr_retiro_acelerado_max.
    PROVISIONAL: TR se calcula sobre esos 3 desafíos (mediana de sus razones), no sobre toda la ventana de 5; si ninguno
    tiene tiempo medido, TR no se puede evaluar y NO se retira (igual que R1). Sin R3, R11, R12 ni preferencia 3.4 (entrega 6 y 7).
    """

    codigo = "R2"
    clave_mensaje = "retiro_automatico"

    def _ultimos(self, ctx: ContextoRegla):
        n = int(ctx.config["retiro_refuerzo"]["desafios_limpios_acelerado"])
        return n, ctx.cierres_recientes[-n:]

    def aplica(self, ctx: ContextoRegla) -> bool:
        rr = ctx.config["retiro_refuerzo"]
        n, ultimos = self._ultimos(ctx)
        if ctx.ns_actual < 1 or ctx.desafios_desde_cambio < n or len(ultimos) < n:
            return False
        intentos = int(rr["intentos_desafio_limpio"])
        if not all(c.resultado == "SA" and c.intentos == intentos for c in ultimos):
            return False
        tr = calcular_indicadores(ultimos).tr
        return tr is not None and redondear(tr) <= rr["tr_retiro_acelerado_max"]

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        n, ultimos = self._ultimos(ctx)
        tr = calcular_indicadores(ultimos).tr
        nuevo = max(NS_MINIMO, ctx.ns_actual - 2)
        return ResultadoRegla(
            nuevo, f"R2 retiro acelerado: {n} desafíos seguidos SA con 1 intento, TR={tr:.2f}; el NS baja de {ctx.ns_actual} a {nuevo}"
        )
