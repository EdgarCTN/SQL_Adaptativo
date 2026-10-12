from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_CODIGO = 4000
Dificultad = Literal["D1", "D2", "D3"]
EstadoUsuario = Literal["sin_iniciar", "en_curso", "resuelto"]


class ConceptoOut(BaseModel):
    codigo: str
    nombre: str


class DesafioResumenOut(BaseModel):
    id: int
    titulo: str
    concepto: ConceptoOut
    dificultad: Dificultad
    tiempo_referencia_seg: int
    estado: EstadoUsuario


class GrupoOut(BaseModel):
    dificultad: Dificultad
    desafios: list[DesafioResumenOut]


class ListaDesafiosOut(BaseModel):
    total: int
    mensaje: str | None = None
    conceptos: list[ConceptoOut]  # conceptos con desafíos disponibles (para el filtro)
    grupos: list[GrupoOut]  # siempre D1, D2 y D3


class SesionResumenOut(BaseModel):
    sesion_id: int
    inicio: datetime
    intentos_realizados: int


class DesafioDetalleOut(BaseModel):
    id: int
    titulo: str
    enunciado: str
    recursos: list[str]
    concepto: ConceptoOut
    dificultad: Dificultad
    esquema_sql: str
    tiempo_referencia_seg: int
    estado: EstadoUsuario
    sesion_en_curso: SesionResumenOut | None = None


class IniciarOut(BaseModel):
    sesion_id: int
    desafio_id: int
    estado: str
    inicio: datetime
    reanudada: bool
    intentos_realizados: int


class IntentoIn(BaseModel):
    codigo: str = Field(max_length=MAX_CODIGO)

    @field_validator("codigo")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Escribe tu consulta antes de enviar.")
        return v


class IntentoOut(BaseModel):
    numero: int
    correcto: bool
    # correcto | resultado_distinto | error_sql | no_permitida | varias_sentencias | tiempo_agotado
    tipo_resultado: str
    mensaje: str
    detalle_tecnico: str | None = None
    columnas: list[str]
    filas: list[list[Any]]
    total_filas: int
    truncado: bool
    desafio_resuelto: bool
    estado_sesion: str
    resultado_cierre: str | None = None
    tiempo_activo_seg: int | None = None
    creado_en: datetime


class AbandonarOut(BaseModel):
    estado: str
    resultado_cierre: str
    tiempo_activo_seg: int
    mensaje: str
