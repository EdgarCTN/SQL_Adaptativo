from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, ahora_utc


class Rol(str, Enum):
    estudiante = "estudiante"
    docente = "docente"
    administrador = "administrador"


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("rol IN ('estudiante','docente','administrador')", name="ck_usuarios_rol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hash_password: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default=Rol.estudiante.value)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[object] = mapped_column(UTCDateTime, default=ahora_utc)
    linea_base_completada: Mapped[bool] = mapped_column(Boolean, default=False)
