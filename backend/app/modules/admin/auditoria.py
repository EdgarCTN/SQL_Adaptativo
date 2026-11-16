"""Registro de auditoría: una función simple que usan el módulo admin y docente/service.py."""
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.admin.models import Auditoria

log = logging.getLogger("app.auditoria")


def registrar_auditoria(
    db: Session,
    usuario_id: int | None,
    accion: str,
    objeto: str,
    detalle: dict | None = None,
    *,
    confirmar: bool = True,
) -> None:
    """Anota quién hizo qué sobre qué objeto.

    `confirmar=True` guarda en el acto y, si falla, lo registra en el log sin romper la acción del usuario.
    `confirmar=False` solo añade la fila a la transacción en curso: se guarda (o se descarta) junto con el cambio.
    """
    db.add(Auditoria(usuario_id=usuario_id, accion=accion, objeto=objeto, detalle=detalle))
    if not confirmar:
        return
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo registrar la auditoría %s sobre %s", accion, objeto)
