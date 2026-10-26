from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.niveles import NS_MAXIMO
from app.modules.motor_retiro.reglas.base import ACCION_SUGERIR, Regla, ResultadoRegla


class R8OmisionMuyDificil(Regla):
    """R8 Omisión «Muy difícil» (Matriz, Tabla 9, bloque 4).

    Condición: el desafío que se acaba de cerrar se omitió por «Muy difícil». No cuenta como fallo ni entra en la
    ventana. Acción: el NS sube 1 (máximo 3) y se ofrece un desafío más básico del mismo concepto (lo busca el motor).
    Si es la segunda omisión «Muy difícil» seguida y el NS ya era 3, se registra para R6 (b), que llega en la
    entrega 5. Umbral (reglas.json): r6_estancamiento.omisiones_muy_dificil_seguidas.
    """

    codigo = "R8"
    clave_mensaje = "refuerzo"
    aplica_en_omision = True

    def aplica(self, ctx: ContextoRegla) -> bool:
        return ctx.omision_motivo == "muy_dificil"

    def ejecutar(self, ctx: ContextoRegla) -> ResultadoRegla:
        minimo_seguidas = int(ctx.config["r6_estancamiento"]["omisiones_muy_dificil_seguidas"])
        ya_en_maximo = ctx.ns_actual >= NS_MAXIMO
        r6_b = ya_en_maximo and ctx.omisiones_muy_dificil_seguidas >= minimo_seguidas
        if ya_en_maximo:
            motivo = "R8 omisión «Muy difícil»: el NS ya está en el máximo"
        else:
            motivo = f"R8 omisión «Muy difícil»: el NS sube de {ctx.ns_actual} a {ctx.ns_actual + 1}"
        if r6_b:
            motivo += f"; {ctx.omisiones_muy_dificil_seguidas} omisiones «Muy difícil» seguidas con NS 3: registrado para R6 (b)"
        return ResultadoRegla(
            min(NS_MAXIMO, ctx.ns_actual + 1),
            motivo,
            accion=ACCION_SUGERIR,
            extra={"r6_b_pendiente": True} if r6_b else {},
        )
