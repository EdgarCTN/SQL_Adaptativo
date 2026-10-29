from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.modules.motor_retiro.contexto import ContextoRegla

# Acciones que una regla pide al motor (la regla solo decide; el motor consulta la base y ejecuta).
ACCION_CAMBIAR_NS = "cambiar_ns"  # el NS cambia (R1, R5; también R8 cuando no hay sugerencia)
ACCION_VERIFICACION = "verificacion"  # asignar un desafío de verificación (R7)
ACCION_SUGERIR = "sugerir"  # ofrecer un desafío más básico del mismo concepto (R8)
ACCION_ESTANCAMIENTO = "estancamiento"  # el NS no cambia; se deriva o se sugiere el concepto previo (R6)
ACCION_MANTENER = "mantener"  # nada que hacer (R4)


@dataclass(frozen=True)
class ResultadoRegla:
    ns_nuevo: int
    motivo: str  # texto técnico para historial y eventos
    accion: str | None = None  # None = cambiar_ns si el NS cambia, mantener si no
    clave_mensaje: str | None = None  # si es None se usa la de la regla (Regla.clave_mensaje)
    extra: dict = field(default_factory=dict)  # datos para el evento del motor (p. ej. r6_b_pendiente)


class Regla(ABC):
    codigo: str
    clave_mensaje: str | None = None  # clave en mensajes_fijos.json para el aviso al estudiante
    aplica_en_omision: bool = False  # R5, R1: miran la ventana y no se evalúan al omitir; R4, R7, R8 sí

    @abstractmethod
    def aplica(self, contexto: ContextoRegla) -> bool: ...

    @abstractmethod
    def ejecutar(self, contexto: ContextoRegla) -> ResultadoRegla: ...


def redondear(x: float) -> float:
    """Evita que 0.7999999 no alcance el umbral 0.8 (misma idea que el redondeo de m)."""
    return round(x, 6)
