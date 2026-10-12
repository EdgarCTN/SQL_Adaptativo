from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class SolicitudAyuda(Base):
    """Una ayuda entregada al estudiante dentro de una sesión de desafío."""

    __tablename__ = "solicitudes_ayuda"
    __table_args__ = (CheckConstraint("tipo_ayuda IN ('AY1','AY2','AY3','AY4')", name="ck_solicitud_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sesion_id: Mapped[int] = mapped_column(ForeignKey("sesiones_desafio.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    desafio_id: Mapped[int] = mapped_column(ForeignKey("desafios.id"), index=True)
    tipo_ayuda: Mapped[str] = mapped_column(String(3))
    momento: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
    fue_respaldo: Mapped[bool] = mapped_column(Boolean, default=False)
    proveedor: Mapped[str] = mapped_column(String(30))
    texto_entregado: Mapped[str] = mapped_column(Text)
    codigo_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    incidente_validacion: Mapped[str | None] = mapped_column(Text, nullable=True)


class ValoracionAyuda(Base):
    """+1 / −1 del estudiante sobre una ayuda. Solo se registra; no influye en nada."""

    __tablename__ = "valoraciones_ayuda"
    __table_args__ = (
        CheckConstraint("valor IN (1, -1)", name="ck_valoracion_valor"),
        UniqueConstraint("solicitud_id", "usuario_id", name="uq_valoracion_solicitud_usuario"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes_ayuda.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    valor: Mapped[int] = mapped_column(Integer)
    creado_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc)
