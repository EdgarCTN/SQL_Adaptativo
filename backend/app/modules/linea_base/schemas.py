from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StrictInt


class ConsentimientoIn(BaseModel):
    acepta: bool


class ConsentimientoOut(BaseModel):
    aceptado: bool
    version: str | None = None
    aceptado_en: datetime | None = None
    mensaje: str


class EstadoOut(BaseModel):
    linea_base_completada: bool
    consentimiento_aceptado: bool
    version_consentimiento: str
    cuestionario_disponible: bool
    cuestionario_id: int | None = None
    siguiente_paso: Literal["consentimiento", "cuestionario", "completado", "no_disponible"]


class CuestionarioOut(BaseModel):
    id: int
    version: int
    introduccion: str = ""
    partes: list[dict[str, Any]]


class RespuestaIn(BaseModel):
    pregunta_id: str = Field(min_length=1, max_length=10)
    # Ids de opción elegidos. Preguntas únicas y de la Parte 2: exactamente uno.
    opciones: list[Annotated[str, Field(max_length=10)]] = Field(default_factory=list, max_length=12)
    confianza: StrictInt | None = None  # Parte 2: 1 a 5 (no se pide si la respuesta es «No sé»)
    omitir: str | None = Field(default=None, max_length=20)  # Parte 2: muy_facil | muy_dificil


class RespuestasIn(BaseModel):
    cuestionario_id: int | None = None
    respuestas: list[RespuestaIn] = Field(max_length=100)


class VerificacionInicialOut(BaseModel):
    """R0/R7: concepto con todos sus ítems (≥ 2) omitidos por «Muy fácil»; se asigna un desafío de verificación."""

    concepto: str
    desafio_id: int
    titulo: str
    dificultad: Literal["D1", "D2", "D3"]
    mensaje: str


class RespuestasOut(BaseModel):
    ok: bool = True
    mensaje: str
    aviso: str | None = None
    linea_base_completada: bool = True
    verificaciones: list[VerificacionInicialOut] = Field(default_factory=list)
