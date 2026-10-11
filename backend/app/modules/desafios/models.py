from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Concepto(Base):
    __tablename__ = "conceptos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    prerrequisito_id: Mapped[int | None] = mapped_column(ForeignKey("conceptos.id"), nullable=True)
