from datetime import datetime

from pydantic import BaseModel


class NivelConceptoOut(BaseModel):
    codigo: str
    nombre: str
    ns: int  # 0-3 (1 por defecto si aún no hay registro)
    desafios_resueltos: int


class CambioNivelOut(BaseModel):
    concepto: str  # nombre del concepto
    ns_anterior: int
    ns_nuevo: int
    texto: str  # mensaje para el estudiante (mensajes_fijos.json)
    fecha: datetime


class AyudasOut(BaseModel):
    AY1: int = 0
    AY2: int = 0
    AY3: int = 0
    AY4: int = 0
    total: int = 0


class ResumenProgresoOut(BaseModel):
    sin_actividad: bool
    sugerencia: str | None = None  # solo si no hay actividad
    desafios_resueltos: int
    desafios_disponibles: int
    sesiones_abandonadas: int
    diagnostico_completado: bool
    niveles: list[NivelConceptoOut]
    ayudas: AyudasOut
    cambios_recientes: list[CambioNivelOut]
