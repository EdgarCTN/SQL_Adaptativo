"""Puntos de enganche al cerrar un desafío.

La entrega 9 conecta aquí el motor de reglas. Hoy no hace nada a propósito.
"""
from sqlalchemy.orm import Session

from app.modules.desafios.models import SesionDesafio


def al_cerrar_desafio(db: Session, sesion: SesionDesafio) -> None:
    """Se invoca ya guardado el cierre (resuelto o abandonado). Vacío hasta la entrega 9."""
    return None
