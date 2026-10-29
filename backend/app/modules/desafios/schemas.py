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
    verificacion: bool = False  # R7: es el desafío de verificación pendiente del estudiante


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
    verificacion: bool = False  # R7: sin ayuda automática; si pide ayuda no cuenta como SA


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


class MensajeMotorOut(BaseModel):
    clave: str
    tipo: str  # retiro | refuerzo | verificacion | sugerencia | estancamiento
    texto: str
    enlace: str | None = None  # ruta del frontend, p. ej. /desafios?concepto=join (R6)


class AjusteNivelOut(BaseModel):
    concepto: str
    ns_anterior: int
    ns_nuevo: int
    motivo: str  # texto para el estudiante


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
    ajuste_nivel: AjusteNivelOut | None = None  # solo si al resolver cambió el nivel de ayuda del concepto
    mensajes: list[MensajeMotorOut] = []  # avisos del motor (p. ej. R6 estancamiento, que no cambia el NS)


class AbandonarOut(BaseModel):
    estado: str
    resultado_cierre: str
    tiempo_activo_seg: int
    mensaje: str
    ajuste_nivel: AjusteNivelOut | None = None
    mensajes: list[MensajeMotorOut] = []


MotivoOmision = Literal["muy_facil", "muy_dificil"]
MSG_MOTIVO_OMISION = "Indica si el desafío te pareció muy fácil o muy difícil."


class OmitirIn(BaseModel):
    motivo: str

    @field_validator("motivo")
    @classmethod
    def _motivo_valido(cls, v: str) -> str:
        if v not in ("muy_facil", "muy_dificil"):
            raise ValueError(MSG_MOTIVO_OMISION)
        return v


class DesafioSugeridoOut(BaseModel):
    id: int
    titulo: str
    dificultad: Dificultad


class VerificacionOut(BaseModel):
    concepto: str
    desafio_id: int
    titulo: str
    dificultad: Dificultad
    mensaje: str


class OmitirOut(BaseModel):
    estado: str
    motivo: MotivoOmision
    mensaje: str
    ajuste_nivel: AjusteNivelOut | None = None  # R8: el NS subió
    sugerido: DesafioSugeridoOut | None = None  # R8: desafío más básico del mismo concepto, o null
    verificacion: VerificacionOut | None = None  # R7: desafío de verificación asignado
    mensajes: list[MensajeMotorOut] = []


class LatidoOut(BaseModel):
    ok: bool = True
    tiempo_activo_seg: int
