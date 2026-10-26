from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class Concepto(Base):
    __tablename__ = "conceptos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    prerrequisito_id: Mapped[int | None] = mapped_column(ForeignKey("conceptos.id"), nullable=True)


class Desafio(Base):
    """Se carga solo por seeds. `solucion_referencia`, `ayudas_respaldo` y `sandbox_setup_sql` nunca salen por la API."""

    __tablename__ = "desafios"
    __table_args__ = (CheckConstraint("dificultad IN ('D1','D2','D3')", name="ck_desafio_dificultad"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160), unique=True)
    enunciado: Mapped[str] = mapped_column(Text)
    recursos: Mapped[Any] = mapped_column(JSON, nullable=True)  # lista de textos breves
    concepto_id: Mapped[int] = mapped_column(ForeignKey("conceptos.id"), index=True)
    dificultad: Mapped[str] = mapped_column(String(2))
    esquema_sql: Mapped[str] = mapped_column(Text)  # CREATE TABLE ... para MOSTRAR al estudiante
    sandbox_setup_sql: Mapped[str] = mapped_column(Text)  # lo ejecuta el sistema (de confianza)
    solucion_referencia: Mapped[str] = mapped_column(Text)
    errores_tipicos: Mapped[Any] = mapped_column(JSON, nullable=True)
    ayudas_respaldo: Mapped[Any] = mapped_column(JSON, nullable=True)  # {"AY1": ..., "AY2": ..., "AY3": ..., "AY4": ...}
    tiempo_referencia_seg: Mapped[int] = mapped_column(Integer)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class SesionDesafio(Base):
    """Una sesión por intento de resolver un desafío. El servidor mide inicio y fin."""

    __tablename__ = "sesiones_desafio"
    __table_args__ = (
        CheckConstraint("estado IN ('en_curso','resuelto','abandonado','omitido')", name="ck_sesion_estado"),
        CheckConstraint(
            "resultado_cierre IS NULL OR resultado_cierre IN ('SA','CP','CE','NR')",
            name="ck_sesion_cierre",
        ),
        CheckConstraint(
            "tiempo_activo_origen IS NULL OR tiempo_activo_origen IN ('latidos','reloj')",
            name="ck_sesion_origen_tiempo",
        ),
        # A lo sumo una sesión en curso por estudiante y desafío (también ante doble clic)
        Index(
            "uq_sesion_en_curso",
            "usuario_id",
            "desafio_id",
            unique=True,
            sqlite_where=text("estado = 'en_curso'"),
            postgresql_where=text("estado = 'en_curso'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    desafio_id: Mapped[int] = mapped_column(ForeignKey("desafios.id"), index=True)
    inicio: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
    fin: Mapped[Any] = mapped_column(UTCDateTime, nullable=True)
    estado: Mapped[str] = mapped_column(String(12), default="en_curso")  # en_curso | resuelto | abandonado | omitido
    resultado_cierre: Mapped[str | None] = mapped_column(String(2), nullable=True)
    # Con latidos se va acumulando; sin latidos, al cerrar vale fin - inicio.
    tiempo_activo_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ultimo_latido_en: Mapped[Any] = mapped_column(UTCDateTime, nullable=True)
    tiempo_activo_origen: Mapped[str | None] = mapped_column(String(8), nullable=True)  # 'latidos' | 'reloj'
    ayuda_mostrada_sola: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # lo usa la ayuda (7B+)


class Intento(Base):
    __tablename__ = "intentos"
    __table_args__ = (UniqueConstraint("sesion_id", "numero", name="uq_intento_sesion_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sesion_id: Mapped[int] = mapped_column(ForeignKey("sesiones_desafio.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    codigo: Mapped[str] = mapped_column(Text)
    correcto: Mapped[bool] = mapped_column(Boolean)
    # {tipo, mensaje, detalle_tecnico, columnas, filas (máx. 20), total_filas, truncado}
    resultado_obtenido: Mapped[Any] = mapped_column(JSON, nullable=True)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
