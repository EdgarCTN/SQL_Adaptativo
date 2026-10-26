"""Único punto por donde el motor produce textos para el estudiante (mensajes_fijos.json).

La entrega de notificaciones (entrega 10) solo tiene que enganchar aquí: las reglas no construyen textos.
Tipos de mensaje: retiro, refuerzo, verificacion, sugerencia.
"""
from dataclasses import dataclass

from app.modules.asistencia.config_llm import cargar_mensajes_fijos

TIPO_RETIRO = "retiro"
TIPO_REFUERZO = "refuerzo"
TIPO_VERIFICACION = "verificacion"
TIPO_SUGERENCIA = "sugerencia"

_TIPO_POR_CLAVE = {
    "retiro_automatico": TIPO_RETIRO,
    "refuerzo": TIPO_REFUERZO,
    "verificacion": TIPO_VERIFICACION,
    "sugerencia_mas_basico": TIPO_SUGERENCIA,
}


@dataclass(frozen=True)
class MensajeEstudiante:
    clave: str
    tipo: str
    texto: str


def texto_fijo(clave: str | None, **marcadores: str) -> str | None:
    """Texto de mensajes_fijos.json con los marcadores {{nombre}} reemplazados; None si no existe o no se puede leer."""
    if not clave:
        return None
    try:
        texto = cargar_mensajes_fijos()["mensajes"][clave]["texto"]
    except (KeyError, OSError, ValueError, TypeError):
        return None
    if not texto:
        return None
    for nombre, valor in marcadores.items():
        texto = texto.replace("{{" + nombre + "}}", valor)
    return texto


def texto_cambio_ns(clave: str | None, concepto: str, ns_anterior: int, ns_nuevo: int) -> str:
    """Aviso de cambio de NS; sin mensaje fijo, uno genérico (provisional)."""
    return texto_fijo(clave, concepto=concepto) or f"Tu nivel de ayuda en {concepto} pasó de {ns_anterior} a {ns_nuevo}."


def mensaje(clave: str, **marcadores: str) -> MensajeEstudiante | None:
    texto = texto_fijo(clave, **marcadores)
    if texto is None:
        return None
    return MensajeEstudiante(clave, _TIPO_POR_CLAVE.get(clave, TIPO_REFUERZO), texto)
