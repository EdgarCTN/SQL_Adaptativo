from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class Auditoria(Base):
    """Cambios de rol y acciones sobre el banco de desafíos. Sin clave foránea a `desafios`: el borrado físico no la toca."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    accion: Mapped[str] = mapped_column(String(40), index=True)  # p. ej. «usuario.cambiar_rol», «desafio.crear»
    objeto: Mapped[str] = mapped_column(String(80))  # p. ej. «usuario:7», «desafio:12»
    detalle: Mapped[Any] = mapped_column(JSON, nullable=True)
    creado_en: Mapped[object] = mapped_column(UTCDateTime, default=ahora_utc, index=True)
