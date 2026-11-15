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


class OpcionDesafioOut(BaseModel):
    id: int
    titulo: str


class IntentoHistorialOut(BaseModel):
    id: int
    sesion_id: int
    desafio_id: int
    desafio: str  # título
    concepto: str  # nombre
    dificultad: str
    numero: int  # número de envío dentro de la sesión
    correcto: bool
    resultado: str  # texto para el estudiante («Correcto», «Error de SQL»…)
    estado_sesion: str  # en_curso | resuelto | abandonado | omitido
    fecha: datetime


class ListaIntentosOut(BaseModel):
    intentos: list[IntentoHistorialOut]
    total: int
    pagina: int
    tam: int
    paginas: int
    desafios: list[OpcionDesafioOut]  # desafíos con intentos del estudiante (opciones del filtro)


class OpcionConceptoOut(BaseModel):
    codigo: str
    nombre: str


class PuntoIndicadoresOut(BaseModel):
    """Indicadores de la ventana y NS vigente justo después de un cierre."""

    sesion_id: int
    concepto: str  # código
    concepto_nombre: str
    fecha: datetime
    ta: float | None = None
    ni: float | None = None
    tr: float | None = None
    ua: float | None = None
    n_ventana: int
    ns: int


class CambioNsOut(BaseModel):
    concepto: str  # código
    concepto_nombre: str
    fecha: datetime
    ns_anterior: int
    ns_nuevo: int
    texto: str  # mensaje para el estudiante, no el motivo técnico


class EvolucionOut(BaseModel):
    concepto: str | None  # código filtrado (None = todos)
    indicadores: list[PuntoIndicadoresOut]
    cambios_ns: list[CambioNsOut]
    conceptos_con_datos: list[OpcionConceptoOut]  # conceptos con historial del estudiante (opciones del filtro)
