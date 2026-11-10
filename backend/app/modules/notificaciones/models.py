from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class Notificacion(Base):
    """Aviso persistente para su dueño; `clave_evento` hace idempotente la creación por evento del motor."""

    __tablename__ = "notificaciones"
    __table_args__ = (
        UniqueConstraint("clave_evento", name="uq_notificaciones_evento"),
        Index("ix_notificaciones_usuario_creada", "usuario_id", "creada_en"),
        Index("ix_notificaciones_usuario_leida", "usuario_id", "leida"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(32))
    texto: Mapped[str] = mapped_column(Text)
    regla: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concepto_id: Mapped[int | None] = mapped_column(ForeignKey("conceptos.id"), nullable=True)
    leida: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    creada_en: Mapped[Any] = mapped_column(UTCDateTime, default=ahora_utc, index=True)
    ajuste_id: Mapped[int | None] = mapped_column(ForeignKey("ajustes_pendientes.id"), nullable=True)
    clave_evento: Mapped[str] = mapped_column(String(180))
