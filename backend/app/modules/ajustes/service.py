"""R13 (pregunta 3.4): retiros de R1 y R2 que esperan al estudiante (`ajustes_pendientes`).

El motor crea el ajuste pendiente (`motor_retiro/retiro_diferido.py`); aquí se lista, se responde y se aplica.
Todo retiro que se aplica pasa por `motor._guardar_cambio_ns(..., es_retiro=True)` con la regla original (R1 o R2),
para que la recaída (R3) siga funcionando.
"""
import logging
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.errores import ErrorApp
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.motor_retiro import mensajes, motor
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.motor_retiro.models import AjustePendiente, EventoMotor
from app.modules.motor_retiro.retiro_diferido import (
    CLAVE_AVISO_PREVIO,
    CLAVE_PREGUNTAR,
    MODO_AVISO_PREVIO,
    ns_y_pausa,
    pendiente_del_concepto,
    sigue_vigente,
)

log = logging.getLogger("app.ajustes")

MSG_NO_ENCONTRADO = "No encontramos ese aviso."
MSG_YA_RESPONDIDO = "Ya respondiste a este aviso."
MSG_CADUCADO = "Este cambio ya no corresponde porque tu nivel de ayuda cambió desde entonces. Seguimos como estás."
MSG_MANTENIDO = "De acuerdo: mantenemos tu nivel de ayuda actual en {concepto}."
MSG_ERROR_GUARDADO = "No pudimos guardar tu respuesta. Inténtalo de nuevo en unos segundos."
MSG_RETIRO_APLICADO = "Tu nivel de ayuda en {concepto} bajó de {antes} a {despues}. Siempre puedes pedir ayuda."


def _texto_pendiente(ajuste: AjustePendiente, concepto: str) -> str:
    clave = CLAVE_AVISO_PREVIO if ajuste.modo == MODO_AVISO_PREVIO else CLAVE_PREGUNTAR
    return mensajes.texto_fijo(clave, concepto=concepto) or f"Vas muy bien con {concepto}. ¿Quieres que te ofrezca menos ayuda?"


def _caducar(ajuste: AjustePendiente, ahora) -> None:
    ajuste.estado, ajuste.resuelto_en = "caducado", ahora


def listar_pendientes(db: Session, usuario: Usuario) -> dict:
    """Ajustes que esperan al estudiante. Los que ya no corresponden (el NS cambió o hay pausa) se marcan `caducado`."""
    filas = db.execute(
        select(AjustePendiente, Concepto)
        .join(Concepto, Concepto.id == AjustePendiente.concepto_id)
        .where(AjustePendiente.usuario_id == usuario.id, AjustePendiente.estado == "pendiente")
        .order_by(AjustePendiente.id)
    ).all()
    salida, ahora, caducados = [], ahora_utc(), False
    for ajuste, concepto in filas:
        _, ns, pausa = ns_y_pausa(db, usuario.id, ajuste.concepto_id)
        if not sigue_vigente(ajuste, ns, pausa):
            _caducar(ajuste, ahora)
            caducados = True
            continue
        salida.append(
            {
                "id": ajuste.id,
                "concepto": {"codigo": concepto.codigo, "nombre": concepto.nombre},
                "modo": ajuste.modo,
                "texto": _texto_pendiente(ajuste, concepto.nombre),
                "creado_en": ajuste.creado_en,
            }
        )
    if caducados:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            log.exception("No se pudieron marcar los ajustes caducados")
    return {"ajustes": salida}


def _aplicar(db: Session, ajuste: AjustePendiente, ahora, sesion_id: int | None, origen: str) -> motor.AjusteNivel:
    """Aplica el retiro (sin confirmar): NS, ventana reiniciada, historial y evento. Queda `aplicado`."""
    fila, _, _ = ns_y_pausa(db, ajuste.usuario_id, ajuste.concepto_id)
    concepto = db.get(Concepto, ajuste.concepto_id)
    motivo = f"R13 (3.4 = {ajuste.modo}): {origen}. {ajuste.motivo}"
    motor._guardar_cambio_ns(
        db, fila, ajuste.usuario_id, ajuste.concepto_id, ajuste.ns_antes, ajuste.ns_nuevo, ajuste.regla, motivo, ahora,
        es_retiro=True,  # R3 reconoce el retiro por esta fila de historial_niveles y por ns_previo_retiro
    )
    ajuste.estado, ajuste.resuelto_en = "aplicado", ahora
    db.add(
        EventoMotor(
            usuario_id=ajuste.usuario_id, concepto_id=ajuste.concepto_id, sesion_id=sesion_id, regla=ajuste.regla,
            ns_antes=ajuste.ns_antes, ns_despues=ajuste.ns_nuevo, resultado="cambio",
            indicadores={"r13": {"preferencia_3_4": ajuste.modo, "ajuste_id": ajuste.id, "origen": origen}},
            detalle=motivo, creado_en=ahora,
        )
    )
    texto = MSG_RETIRO_APLICADO.format(concepto=concepto.nombre, antes=ajuste.ns_antes, despues=ajuste.ns_nuevo)
    return motor.AjusteNivel(concepto.nombre, ajuste.ns_antes, ajuste.ns_nuevo, mensajes.texto_fijo("retiro_automatico", concepto=concepto.nombre) or texto)


def responder(db: Session, usuario: Usuario, ajuste_id: int, accion: str) -> dict:
    ajuste = db.get(AjustePendiente, ajuste_id)
    if ajuste is None or ajuste.usuario_id != usuario.id:  # no se distingue «no existe» de «es de otro»
        raise ErrorApp(MSG_NO_ENCONTRADO, 404)
    if ajuste.estado != "pendiente":
        raise ErrorApp(MSG_YA_RESPONDIDO, 409)
    concepto = db.get(Concepto, ajuste.concepto_id)
    _, ns, pausa = ns_y_pausa(db, usuario.id, ajuste.concepto_id)
    ahora = ahora_utc()
    try:
        if not sigue_vigente(ajuste, ns, pausa):
            _caducar(ajuste, ahora)
            db.commit()
            return {"estado": "caducado", "mensaje": MSG_CADUCADO, "ajuste_nivel": None}
        if accion == "mantener":
            ajuste.estado, ajuste.resuelto_en = "mantenido", ahora
            db.add(
                EventoMotor(
                    usuario_id=usuario.id, concepto_id=ajuste.concepto_id, regla=ajuste.regla, ns_antes=ns, ns_despues=ns,
                    resultado="mantiene", indicadores={"r13": {"preferencia_3_4": ajuste.modo, "ajuste_id": ajuste.id, "respuesta": "mantener"}},
                    detalle=f"R13 (3.4 = {ajuste.modo}): el estudiante mantiene la ayuda; el NS sigue en {ns}", creado_en=ahora,
                )
            )
            db.commit()
            return {"estado": "mantenido", "mensaje": MSG_MANTENIDO.format(concepto=concepto.nombre), "ajuste_nivel": None}
        nivel = _aplicar(db, ajuste, ahora, None, "el estudiante aceptó el retiro")
        db.commit()
        return {"estado": "aplicado", "mensaje": nivel.motivo, "ajuste_nivel": asdict(nivel)}
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo guardar la respuesta al ajuste %s", ajuste_id)
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)


def aplicar_al_iniciar(db: Session, sesion: SesionDesafio) -> tuple[MensajeEstudiante, ...]:
    """Al iniciar un desafío nuevo: aplica el retiro `aviso_previo` pendiente del concepto (no se pulsó «Mantener la
    ayuda»). Va antes de R12. Nunca rompe el inicio: ante cualquier fallo no cambia nada y deja el error en eventos_motor."""
    try:
        desafio = db.get(Desafio, sesion.desafio_id)
        ajuste = pendiente_del_concepto(db, sesion.usuario_id, desafio.concepto_id, MODO_AVISO_PREVIO)
        if ajuste is None:
            return ()
        _, ns, pausa = ns_y_pausa(db, sesion.usuario_id, desafio.concepto_id)
        ahora = ahora_utc()
        if not sigue_vigente(ajuste, ns, pausa):
            _caducar(ajuste, ahora)
            db.commit()
            return ()
        nivel = _aplicar(db, ajuste, ahora, sesion.id, "aviso previo sin respuesta: se aplica al iniciar el siguiente desafío")
        db.commit()
        m = mensajes.mensaje("retiro_automatico", concepto=nivel.concepto)
        return (m,) if m else ()
    except Exception as e:  # noqa: BLE001  (iniciar un desafío nunca se rompe)
        log.exception("Falló la aplicación del retiro pendiente (sesión %s): no se cambia nada", sesion.id)
        db.rollback()
        motor._registrar_error(db, sesion.id, sesion.usuario_id, e)
        return ()
