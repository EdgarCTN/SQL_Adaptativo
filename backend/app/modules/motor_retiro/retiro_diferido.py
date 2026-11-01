"""R13, preferencia 3.4 (cómo retirar la ayuda): qué hace el motor cuando R1 o R2 deciden retirar.

- `automatico` (y sin preferencia guardada): el retiro se aplica en el acto, como antes de la entrega 7.
- `aviso_previo`: no se aplica; queda un ajuste pendiente que se aplica al iniciar el siguiente desafío del concepto
  salvo que el estudiante pulse «Mantener la ayuda» (PROVISIONAL: «siguiente» = del mismo concepto).
- `preguntar`: queda un ajuste pendiente que solo se aplica si el estudiante acepta.
- `mantener`: no se retira ni se avisa; el motor solo registra que se cumplió el criterio (PROVISIONAL: se respeta siempre,
  no solo al inicio; la Matriz deja abierta esa decisión).

Este módulo no importa `motor.py`: el motor lo llama al decidir y `modules/ajustes` aplica o responde los pendientes.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.linea_base.models import LineaBaseResultado, NivelSoporte
from app.modules.motor_retiro.models import AjustePendiente
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO

MODO_AUTOMATICO = "automatico"
MODO_AVISO_PREVIO = "aviso_previo"
MODO_PREGUNTAR = "preguntar"
MODO_MANTENER = "mantener"
MODOS = (MODO_AUTOMATICO, MODO_AVISO_PREVIO, MODO_PREGUNTAR, MODO_MANTENER)  # códigos de la pregunta 3.4

CLAVE_AVISO_PREVIO = "retiro_aviso_previo"
CLAVE_PREGUNTAR = "retiro_preguntar"
CLAVE_MANTENER = "retiro_mantener_nivel"  # sin texto: el estudiante no ve ningún mensaje


@dataclass(frozen=True)
class DecisionRetiro:
    """El retiro NO se aplica ahora. `ajuste` es el pendiente (None con `mantener`); `nuevo` indica si se creó ahora."""

    modo: str
    ajuste: AjustePendiente | None
    nuevo: bool
    clave_mensaje: str | None  # mensaje fijo para el estudiante; None si no hay nada que mostrar
    detalle: str  # texto técnico para eventos_motor


def preferencia_retiro(db: Session, usuario_id: int) -> str:
    """Código de la pregunta 3.4 del diagnóstico; `automatico` si no hay resultado, falta la pregunta o el código no se conoce."""
    preferencias = db.scalar(select(LineaBaseResultado.preferencias).where(LineaBaseResultado.usuario_id == usuario_id))
    modo = preferencias.get("3.4") if isinstance(preferencias, dict) else None
    return modo if modo in MODOS else MODO_AUTOMATICO


def ns_y_pausa(db: Session, usuario_id: int, concepto_id: int) -> tuple[NivelSoporte | None, int, int]:
    """Fila de niveles_soporte (puede no existir), NS vigente y desafíos que faltan de pausa de R1 y R2."""
    fila = db.scalar(select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto_id))
    if fila is None:
        return None, NS_POR_DEFECTO, 0
    return fila, int(fila.ns), int(fila.pausa_retiros_restante or 0)


def sigue_vigente(ajuste: AjustePendiente, ns_actual: int, pausa: int) -> bool:
    """El retiro solo corresponde si el NS es el de cuando se propuso (nadie lo movió entre tanto) y no hay pausa."""
    return ns_actual == ajuste.ns_antes and pausa == 0


def pendiente_del_concepto(db: Session, usuario_id: int, concepto_id: int, modo: str | None = None) -> AjustePendiente | None:
    consulta = select(AjustePendiente).where(
        AjustePendiente.usuario_id == usuario_id,
        AjustePendiente.concepto_id == concepto_id,
        AjustePendiente.estado == "pendiente",
    )
    if modo is not None:
        consulta = consulta.where(AjustePendiente.modo == modo)
    return db.scalar(consulta.order_by(AjustePendiente.id.desc()).limit(1))


def decidir(
    db: Session, usuario_id: int, concepto_id: int, sesion_id: int | None, regla: str, ns_antes: int, ns_nuevo: int,
    motivo: str, ahora, ns_actual: int, pausa: int,
) -> DecisionRetiro | None:
    """None si el retiro se aplica ya (`automatico`). Con `aviso_previo` o `preguntar` crea el ajuste pendiente (sin
    confirmar la transacción) salvo que ya haya uno vigente en el concepto; uno vencido se marca `caducado`."""
    modo = preferencia_retiro(db, usuario_id)
    if modo == MODO_AUTOMATICO:
        return None
    if modo == MODO_MANTENER:
        return DecisionRetiro(
            modo, None, False, CLAVE_MANTENER,
            f"R13 (3.4 = mantener): se cumplió el criterio de {regla} y no se retira (NS {ns_antes}); {motivo}",
        )
    previo = pendiente_del_concepto(db, usuario_id, concepto_id)
    if previo is not None:
        if sigue_vigente(previo, ns_actual, pausa):
            return DecisionRetiro(
                modo, previo, False, None,
                f"R13 (3.4 = {modo}): se cumplió otra vez el criterio de {regla}; ya hay un retiro pendiente (id {previo.id})",
            )
        previo.estado, previo.resuelto_en = "caducado", ahora
        db.flush()  # libera el índice de «un pendiente por concepto» antes de insertar el nuevo
    ajuste = AjustePendiente(
        usuario_id=usuario_id, concepto_id=concepto_id, sesion_id=sesion_id, regla=regla, modo=modo,
        ns_antes=ns_antes, ns_nuevo=ns_nuevo, motivo=motivo, estado="pendiente", creado_en=ahora,
    )
    db.add(ajuste)
    db.flush()  # necesita el id para el mensaje
    clave = CLAVE_AVISO_PREVIO if modo == MODO_AVISO_PREVIO else CLAVE_PREGUNTAR
    return DecisionRetiro(
        modo, ajuste, True, clave,
        f"R13 (3.4 = {modo}): {regla} propone retirar de {ns_antes} a {ns_nuevo}; queda pendiente (id {ajuste.id}). {motivo}",
    )
