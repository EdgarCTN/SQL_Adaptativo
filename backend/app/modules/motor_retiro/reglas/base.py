from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.motor_retiro.contexto import ContextoRegla


@dataclass(frozen=True)
class ResultadoRegla:
    ns_nuevo: int
    motivo: str  # texto técnico para historial y eventos


class Regla(ABC):
    codigo: str
    clave_mensaje: str | None = None  # clave en mensajes_fijos.json para el aviso al estudiante

    @abstractmethod
    def aplica(self, contexto: ContextoRegla) -> bool: ...

    @abstractmethod
    def ejecutar(self, contexto: ContextoRegla) -> ResultadoRegla: ...


def redondear(x: float) -> float:
    """Evita que 0.7999999 no alcance el umbral 0.8 (misma idea que el redondeo de m)."""
    return round(x, 6)
