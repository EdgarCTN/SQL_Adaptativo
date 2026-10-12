from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class HistorialNivel(Base):
    """Cada cambio de NS de un estudiante en un concepto."""

    __tablename__ = "historial_niveles"
    __table_args__ = (
        CheckConstraint("ns_anterior BETWEEN 0 AND 3 AND ns_nuevo BETWEEN 0 AND 3", name="ck_historial_ns"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    concepto_id: Mapped[int] = mapped_column(ForeignKey("conceptos.id"))
    ns_anterior: Mapped[int] = mapped_column(Integer)
    ns_nuevo: Mapped[int] = mapped_column(Integer)
    regla: Mapped[str] = mapped_column(String(10))
    motivo: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)


class EventoMotor(Base):
    """Cada ejecución del motor al cerrar un desafío (cambie o no el NS, o falle)."""

    __tablename__ = "eventos_motor"
    __table_args__ = (CheckConstraint("resultado IN ('cambio','mantiene','error')", name="ck_evento_resultado"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    concepto_id: Mapped[int | None] = mapped_column(ForeignKey("conceptos.id"), nullable=True)
    sesion_id: Mapped[int | None] = mapped_column(ForeignKey("sesiones_desafio.id"), nullable=True, index=True)
    regla: Mapped[str | None] = mapped_column(String(10), nullable=True)  # None si falló antes de evaluar
    ns_antes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ns_despues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resultado: Mapped[str] = mapped_column(String(10))
    indicadores: Mapped[Any] = mapped_column(JSON, nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
