"""Puntos de enganche al cerrar un desafío."""
from sqlalchemy.orm import Session

from app.modules.desafios.models import SesionDesafio
from app.modules.motor_retiro.motor import AjusteNivel, ResultadoMotor, cerrar_desafio, cerrar_omision


def al_cerrar_desafio(db: Session, sesion: SesionDesafio) -> AjusteNivel | None:
    """Se invoca ya guardado el cierre (resuelto o abandonado). Ejecuta el motor de reglas (R5, R1, R4)."""
    return cerrar_desafio(db, sesion)


def al_omitir_desafio(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """Se invoca ya guardada la omisión (sesión `omitido` y fila en `omisiones`). Ejecuta R8, R7 y R4."""
    return cerrar_omision(db, sesion)
