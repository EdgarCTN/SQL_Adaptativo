from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.reglas.base import ACCION_VERIFICACION, Regla, ResultadoRegla


class R7OmisionMuyFacil(Regla):
    """R7 Omisión «Muy fácil» (Matriz, Tabla 9, bloque 4).

    Condición: el desafío que se acaba de cerrar se omitió por «Muy fácil» y el concepto acumula al menos 2 omisiones
    de ese tipo (línea base + desafíos, desde la última verificación asignada). No retira por sí sola: el NS no
    cambia y el motor asigna un desafío de verificación sin ayuda automática. El contador se reinicia al asignarlo.
    Si ya hay una verificación pendiente en el concepto, no se asigna otra.
    Umbral (reglas.json): r7_muy_facil.omisiones_para_verificacion.
    """

    codigo = "R7"
    clave_mensaje = "verificacion"
    aplica_en_omision = True

    def aplica(self, ctx: ContextoRegla) -> bool:
        if ctx.omision_motivo != "muy_facil" or ctx.verificacion_pendiente:
            return False
        return ctx.omisiones_muy_facil >= int(ctx.config["r7_muy_facil"]["omisiones_para_verificacion"])

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        return ResultadoRegla(
            ctx.ns_actual,
            f"R7 omisión «Muy fácil»: {ctx.omisiones_muy_facil} omisiones acumuladas, se asigna un desafío de verificación",
            accion=ACCION_VERIFICACION,
        )
