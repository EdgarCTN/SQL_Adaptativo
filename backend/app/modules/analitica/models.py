from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Float, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class IndicadorHistorico(Base):
    """Una fila por cierre de desafío: indicadores de la ventana con la que decidió el motor y el NS resultante."""

    __tablename__ = "indicadores_historicos"
    __table_args__ = (
        UniqueConstraint("sesion_id", name="uq_indhist_sesion"),
        CheckConstraint("ns BETWEEN 0 AND 3", name="ck_indhist_ns"),
        Index("ix_indhist_usuario_concepto", "usuario_id", "concepto_id", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    concepto_id: Mapped[int] = mapped_column(ForeignKey("conceptos.id"))
    sesion_id: Mapped[int] = mapped_column(ForeignKey("sesiones_desafio.id"))
    ta: Mapped[float | None] = mapped_column(Float, nullable=True)
    ni: Mapped[float | None] = mapped_column(Float, nullable=True)
    tr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ua: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_ventana: Mapped[int] = mapped_column(Integer)
    ns: Mapped[int] = mapped_column(Integer)  # NS vigente tras el cierre
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
