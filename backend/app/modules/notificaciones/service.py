import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApp
from app.modules.auth.models import Usuario
from app.modules.motor_retiro import mensajes as mensajes_motor
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.notificaciones.models import Notificacion

log = logging.getLogger("app.notificaciones")
MSG_NO_ENCONTRADA = "No encontramos esa notificación."
MSG_ERROR_GUARDADO = "No pudimos guardar el cambio. Inténtalo de nuevo en unos segundos."
_TIPOS_NOTIFICABLES = {
    mensajes_motor.TIPO_RETIRO,
    mensajes_motor.TIPO_REFUERZO,
    mensajes_motor.TIPO_VERIFICACION,
    mensajes_motor.TIPO_SUGERENCIA,
    mensajes_motor.TIPO_ESTANCAMIENTO,
    mensajes_motor.TIPO_RECAIDA,
    mensajes_motor.TIPO_CAMBIO_DIFICULTAD,
    mensajes_motor.TIPO_REENGANCHE,
    mensajes_motor.TIPO_RETIRO_AVISO,
    mensajes_motor.TIPO_RETIRO_PREGUNTA,
    mensajes_motor.TIPO_REFLEXION,
    mensajes_motor.TIPO_SOBRECONFIANZA,
}


def registrar_mensajes(
    db: Session,
    usuario_id: int,
    clave_evento: str,
    items: list[MensajeEstudiante] | tuple[MensajeEstudiante, ...],
    concepto_id: int | None = None,
) -> None:
    """Persiste mensajes del motor una sola vez por origen; nunca interrumpe el flujo que produjo el aviso."""
    pendientes = []
    for indice, mensaje in enumerate(items):
        if mensaje.tipo not in _TIPOS_NOTIFICABLES:
            continue
        clave = f"{clave_evento}:{indice}"
        if db.scalar(select(Notificacion.id).where(Notificacion.clave_evento == clave)) is not None:
            continue
        pendientes.append(Notificacion(
            usuario_id=usuario_id,
            tipo=mensaje.tipo,
            texto=mensaje.texto,
            regla=mensaje.regla or mensajes_motor.regla_de(mensaje.clave),
            concepto_id=concepto_id,
            leida=False,
            ajuste_id=mensaje.ajuste_id,
            clave_evento=clave,
        ))
    if not pendientes:
        return
    try:
        db.add_all(pendientes)
        db.commit()
    except IntegrityError:
        # Dos reintentos del mismo evento pueden competir: la clave única conserva una sola copia.
        db.rollback()
        log.info("Se omitió una notificación duplicada para el evento %s", clave_evento)
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudieron guardar notificaciones del evento %s", clave_evento)


def registrar_reenganche(db: Session, usuario: Usuario, texto: str, evento_id: int | None) -> None:
    if evento_id is None:
        log.warning("No se guardó el reenganche del usuario %s: no se encontró el evento R14", usuario.id)
        return
    mensaje = MensajeEstudiante("reenganche", mensajes_motor.TIPO_REENGANCHE, texto, regla="R14")
    registrar_mensajes(db, usuario.id, f"R14:{evento_id}", [mensaje])


def listar(db: Session, usuario: Usuario) -> dict:
    filas = list(db.scalars(
        select(Notificacion)
        .where(Notificacion.usuario_id == usuario.id)
        .order_by(Notificacion.creada_en.desc(), Notificacion.id.desc())
    ))
    no_leidas = sum(1 for fila in filas if not fila.leida)
    return {"notificaciones": [{
        "id": fila.id, "tipo": fila.tipo, "texto": fila.texto, "regla": fila.regla,
        "concepto_id": fila.concepto_id, "leida": fila.leida, "creada_en": fila.creada_en,
        "ajuste_id": fila.ajuste_id,
    } for fila in filas], "no_leidas": no_leidas}


def marcar_leida(db: Session, usuario: Usuario, notificacion_id: int) -> dict:
    fila = db.get(Notificacion, notificacion_id)
    if fila is None or fila.usuario_id != usuario.id:
        raise ErrorApp(MSG_NO_ENCONTRADA, 404)
    if not fila.leida:
        fila.leida = True
        _guardar(db)
    return {"ok": True, "id": fila.id}


def marcar_todas(db: Session, usuario: Usuario) -> dict:
    try:
        resultado = db.execute(
            update(Notificacion)
            .where(Notificacion.usuario_id == usuario.id, Notificacion.leida.is_(False))
            .values(leida=True)
        )
        db.commit()
        return {"ok": True, "actualizadas": resultado.rowcount or 0}
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudieron marcar como leídas las notificaciones del usuario %s", usuario.id)
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)


def marcar_ajuste_leido(db: Session, usuario_id: int, ajuste_id: int) -> None:
    """Marca el aviso accionable como leído cuando el ajuste se acepta, mantiene, caduca o se aplica."""
    db.execute(
        update(Notificacion)
        .where(Notificacion.usuario_id == usuario_id, Notificacion.ajuste_id == ajuste_id)
        .values(leida=True)
    )


def _guardar(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo guardar el estado de una notificación")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
