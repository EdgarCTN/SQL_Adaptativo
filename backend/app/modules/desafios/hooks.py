"""Puntos de enganche al cerrar un desafío."""
from sqlalchemy.orm import Session

from app.modules.desafios.models import SesionDesafio
from app.modules.motor_retiro.motor import ResultadoMotor, cerrar_desafio_con_mensajes, cerrar_omision, iniciar_desafio


def al_cerrar_desafio(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """Se invoca ya guardado el cierre (resuelto o abandonado). Ejecuta el motor de reglas (R3, R6, R5, R2, R1, R4)."""
    return cerrar_desafio_con_mensajes(db, sesion)


def al_omitir_desafio(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """Se invoca ya guardada la omisión (sesión `omitido` y fila en `omisiones`). Ejecuta R6 (b), R8, R7 y R4."""
    return cerrar_omision(db, sesion)


def al_iniciar_desafio(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """Se invoca al crear una sesión nueva (no al reanudar una en curso). Ejecuta R12 (cambio de dificultad)."""
    return iniciar_desafio(db, sesion)
