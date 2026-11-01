"""R12 Cambio de dificultad (Matriz, Tabla 9, bloque 6). Decisión pura: no toca la base de datos.

Condición (definición operativa PROVISIONAL: la Matriz no dice cuándo «pasa» el estudiante): inicia un desafío de una
dificultad mayor a la más alta ya cerrada (resuelta o abandonada) en ese concepto, y mayor también que la de cualquier
otro desafío del concepto que ya tenga en curso (así un segundo desafío de la misma dificultad no repite la regla).
Sin desafíos cerrados en el concepto no hay cambio: es el primero.
Efecto: el NS pasa a max(NS actual, ns_minimo_tras_cambio) y R1 y R2 se pausan N desafíos (el que se inicia cuenta como el primero).
Umbrales (reglas.json): r12_cambio_dificultad.ns_minimo_tras_cambio, recaida_y_pausas.desafios_sin_retiro_tras_recaida_o_cambio_dificultad.
"""
from dataclasses import dataclass

RANGO = {"D1": 1, "D2": 2, "D3": 3}


@dataclass(frozen=True)
class DecisionCambioDificultad:
    ns_nuevo: int
    cambia_ns: bool
    pausa_retiros: int
    motivo: str


def evaluar_cambio_dificultad(
    ns_actual: int,
    dificultad_nueva: str,
    mayor_cerrada: str | None,
    mayor_en_curso: str | None,
    config: dict,
) -> DecisionCambioDificultad | None:
    """None si el desafío que se inicia no es un cambio de dificultad."""
    if mayor_cerrada is None:
        return None
    nueva = RANGO[dificultad_nueva]
    if nueva <= RANGO[mayor_cerrada] or (mayor_en_curso is not None and nueva <= RANGO[mayor_en_curso]):
        return None
    ns_minimo = int(config["r12_cambio_dificultad"]["ns_minimo_tras_cambio"])
    pausa = int(config["recaida_y_pausas"]["desafios_sin_retiro_tras_recaida_o_cambio_dificultad"])
    ns_nuevo = max(ns_actual, ns_minimo)
    return DecisionCambioDificultad(
        ns_nuevo,
        ns_nuevo != ns_actual,
        pausa,
        f"R12 cambio de dificultad: inicia {dificultad_nueva} y lo más alto cerrado era {mayor_cerrada}; "
        f"NS {ns_actual} → {ns_nuevo} y R1 y R2 se pausan {pausa} desafíos",
    )
