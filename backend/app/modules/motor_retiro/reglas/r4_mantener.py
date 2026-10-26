from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla


class R4Mantener(Regla):
    """R4 Mantener (Matriz, Tabla 9): regla por defecto.

    Condición: no aplica ninguna otra regla (p. ej. TA entre 0.50 y 0.80 con NI < 4, o TA alta con tiempo alto
    o muchos intentos). Acción: el NS no cambia. También es lo que ocurre con datos insuficientes (menos de
    ventana.minimo_desafios_desde_cambio desafíos desde el último cambio).
    """

    codigo = "R4"
    aplica_en_omision = True

    def aplica(self, ctx: ContextoRegla) -> bool:
        return True

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        minimo = ctx.config["ventana"]["minimo_desafios_desde_cambio"]
        if ctx.omision_motivo is not None:
            motivo = f"R4 mantener: omisión «{ctx.omision_motivo}» registrada, sin efecto sobre el NS ni sobre la ventana"
        elif ctx.desafios_desde_cambio < minimo:
            motivo = f"R4 mantener: datos insuficientes ({ctx.desafios_desde_cambio} de {minimo} desafíos desde el último cambio)"
        else:
            motivo = "R4 mantener: no corresponde ninguna otra regla"
        return ResultadoRegla(ctx.ns_actual, motivo)
