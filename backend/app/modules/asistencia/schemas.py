from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AyudaIn(BaseModel):
    mensaje_estudiante: str | None = Field(default=None, max_length=5000)

    @field_validator("mensaje_estudiante")
    @classmethod
    def _vacio_a_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class AyudaOut(BaseModel):
    solicitud_id: int | None = None  # None: solo se recordó que ya vio la solución
    tipo_ayuda: Literal["AY1", "AY2", "AY3", "AY4"] | None = None
    mensaje: str | None = None
    codigo_sql: str | None = None
    etiquetas: list[str] = []  # rótulos que debe mostrar la ayuda (llm.json)
    fue_respaldo: bool = False
    reformulada: bool = False
    sugerencia: str | None = None  # al recibir un tipo menor por faltar fallos
    aviso: str | None = None  # mensaje fijo (p. ej. solucion_ya_mostrada)
    desafio_marcado_nr: bool = False


class ValoracionIn(BaseModel):
    valor: int

    @field_validator("valor")
    @classmethod
    def _valor(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("debe ser 1 (útil) o -1 (no útil).")
        return v


class ValoracionOut(BaseModel):
    ok: bool
    valor: int
