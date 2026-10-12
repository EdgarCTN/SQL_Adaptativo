"""Puntos de enganche al cerrar un desafío."""
from sqlalchemy.orm import Session

from app.modules.desafios.models import SesionDesafio
from app.modules.motor_retiro.motor import AjusteNivel, cerrar_desafio


def al_cerrar_desafio(db: Session, sesion: SesionDesafio) -> AjusteNivel | None:
    """Se invoca ya guardado el cierre (resuelto o abandonado). Ejecuta el motor de reglas (R5, R1, R4)."""
    return cerrar_desafio(db, sesion)
