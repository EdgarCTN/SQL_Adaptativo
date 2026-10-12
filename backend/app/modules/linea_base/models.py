from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class Consentimiento(Base):
    """Solo se guarda cuando el estudiante ACEPTA."""

    __tablename__ = "consentimientos"
    __table_args__ = (UniqueConstraint("usuario_id", "version", name="uq_consentimiento_usuario_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    version: Mapped[str] = mapped_column(String(20))
    aceptado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class LineaBaseCuestionario(Base):
    __tablename__ = "linea_base_cuestionarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    contenido: Mapped[Any] = mapped_column(JSON)  # incluye `correcta`: nunca se sirve tal cual
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class LineaBaseRespuesta(Base):
    """Una fila por pregunta respondida (las omitidas van a `omisiones`)."""

    __tablename__ = "linea_base_respuestas"
    __table_args__ = (
        UniqueConstraint("usuario_id", "cuestionario_id", "pregunta_id", name="uq_lb_respuesta"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    cuestionario_id: Mapped[int] = mapped_column(ForeignKey("linea_base_cuestionarios.id"))
    pregunta_id: Mapped[str] = mapped_column(String(10))
    parte: Mapped[int] = mapped_column(Integer)  # 1, 2 o 3
    opciones: Mapped[Any] = mapped_column(JSON)  # ids de opción elegidos, p. ej. ["c"] o ["a","d"]
    confianza: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5; vacío si «No sé»
    es_no_se: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class LineaBaseResultado(Base):
    """Resultado del diagnóstico (3B). Los datos crudos siguen en linea_base_respuestas y omisiones."""

    __tablename__ = "linea_base_resultados"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    cuestionario_id: Mapped[int] = mapped_column(ForeignKey("linea_base_cuestionarios.id"))
    m_por_item: Mapped[Any] = mapped_column(JSON, nullable=True)
    m_por_concepto: Mapped[Any] = mapped_column(JSON, nullable=True)
    m_por_nivel: Mapped[Any] = mapped_column(JSON, nullable=True)
    m_global: Mapped[float | None] = mapped_column(Float, nullable=True)
    dificultad_inicial: Mapped[str | None] = mapped_column(String(3), nullable=True)  # se guarda, no se aplica
    ns_inicial_por_concepto: Mapped[Any] = mapped_column(JSON, nullable=True)
    preferencias: Mapped[Any] = mapped_column(JSON, nullable=True)
    banderas_iniciales: Mapped[Any] = mapped_column(JSON, nullable=True)
    contexto: Mapped[Any] = mapped_column(JSON, nullable=True)  # Parte 1 cruda (1.1 a 1.6)
    reglas_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class NivelSoporte(Base):
    __tablename__ = "niveles_soporte"
    __table_args__ = (
        UniqueConstraint("usuario_id", "concepto_id", name="uq_ns_usuario_concepto"),
        CheckConstraint("ns BETWEEN 0 AND 3", name="ck_ns_rango"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    concepto_id: Mapped[int] = mapped_column(ForeignKey("conceptos.id"))
    ns: Mapped[int] = mapped_column(Integer)
    ultimo_cambio_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
    desafios_desde_cambio: Mapped[int] = mapped_column(Integer, default=0)
    ns_maximo_historico: Mapped[int] = mapped_column(Integer)


class Omision(Base):
    __tablename__ = "omisiones"
    __table_args__ = (
        CheckConstraint("motivo IN ('muy_facil','muy_dificil')", name="ck_omision_motivo"),
        CheckConstraint("origen IN ('linea_base','desafio')", name="ck_omision_origen"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    concepto_id: Mapped[int] = mapped_column(ForeignKey("conceptos.id"))
    desafio_id: Mapped[int | None] = mapped_column(ForeignKey("desafios.id"), nullable=True)
    motivo: Mapped[str] = mapped_column(String(20))
    origen: Mapped[str] = mapped_column(String(20))
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
