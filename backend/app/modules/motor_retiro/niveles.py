from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.modules.linea_base.models import NivelSoporte

NS_POR_DEFECTO = 1  # sin registro en niveles_soporte


class NivelSoporteService:
    """Lee el NS vigente de un estudiante en un concepto desde la tabla niveles_soporte."""

    def __init__(self, db: Session | None = None):
        self._db = db

    def obtener(self, usuario_id: int, concepto_id: int) -> int:
        if self._db is not None:
            return self._leer(self._db, usuario_id, concepto_id)
        with SessionLocal() as db:
            return self._leer(db, usuario_id, concepto_id)

    @staticmethod
    def _leer(db: Session, usuario_id: int, concepto_id: int) -> int:
        ns = db.scalar(
            select(NivelSoporte.ns).where(
                NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto_id
            )
        )
        return NS_POR_DEFECTO if ns is None else int(ns)

NS_MINIMO = 0  # estructural (la Matriz define NS de 0 a 3)
NS_MAXIMO = 3
