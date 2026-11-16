from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.modules.desafios.schemas import ConceptoOut, Dificultad

Recurso = Annotated[str, StringConstraints(max_length=300)]


class AyudaIn(BaseModel):
    mensaje: str = Field(default="", max_length=2000)
    codigo_sql: str | None = Field(default=None, max_length=4000)


class AyudasIn(BaseModel):
    AY1: AyudaIn = Field(default_factory=AyudaIn)
    AY2: AyudaIn = Field(default_factory=AyudaIn)
    AY3: AyudaIn = Field(default_factory=AyudaIn)
    AY4: AyudaIn = Field(default_factory=AyudaIn)


class ErrorTipicoIn(BaseModel):
    descripcion: str = Field(default="", max_length=500)
    ejemplo: str = Field(default="", max_length=4000)


class DesafioIn(BaseModel):
    """Todo es opcional a propósito: la validación automática lista los problemas campo por campo."""

    titulo: str = Field(default="", max_length=160)
    enunciado: str = Field(default="", max_length=6000)
    recursos: list[Recurso] = Field(default_factory=list, max_length=10)
    concepto: str = Field(default="", max_length=50, description="Código del concepto")
    dificultad: str = Field(default="", max_length=2)
    esquema_sql: str = Field(default="", max_length=20_000)
    sandbox_setup_sql: str = Field(default="", max_length=50_000)
    solucion_referencia: str = Field(default="", max_length=4000)
    errores_tipicos: list[ErrorTipicoIn] = Field(default_factory=list, max_length=10)
    ayudas_respaldo: AyudasIn = Field(default_factory=AyudasIn)
    tiempo_referencia_seg: int | None = Field(default=None, ge=1, le=7200, description="Vacío = el de reglas.json")
    confirmar_cambio: bool = Field(default=False, description="Solo PUT: confirma cambiar solución o setup de un desafío ya usado")


class AyudaOut(BaseModel):
    mensaje: str
    codigo_sql: str | None = None


class ErrorTipicoOut(BaseModel):
    descripcion: str
    ejemplo: str


class DesafioFilaOut(BaseModel):
    id: int
    titulo: str
    concepto: ConceptoOut
    dificultad: Dificultad
    tiempo_referencia_seg: int
    activo: bool
    n_sesiones: int
    creado_en: datetime | None = None


class ListaDocenteOut(BaseModel):
    total: int
    desafios: list[DesafioFilaOut]


class DesafioDocenteOut(DesafioFilaOut):
    """Solo para docente y administrador: incluye los campos que el estudiante nunca recibe."""

    enunciado: str
    recursos: list[str]
    esquema_sql: str
    sandbox_setup_sql: str
    solucion_referencia: str
    errores_tipicos: list[ErrorTipicoOut]
    ayudas_respaldo: dict[str, AyudaOut]


class OpcionesOut(BaseModel):
    conceptos: list[ConceptoOut]
    dificultades: list[Dificultad]
    tiempos_referencia: dict[str, int]
    n_errores_tipicos: int


class ProblemaOut(BaseModel):
    campo: str
    mensaje: str


class ValidacionOut(BaseModel):
    valido: bool
    problemas: list[ProblemaOut]


class MensajeDocenteOut(BaseModel):
    ok: bool = True
    mensaje: str
