"""Banderas iniciales de la línea base (R9 dependencia, R11 sobreconfianza) y registro de activaciones en eventos_motor.

Las banderas llegan al LLM solo como los códigos de config/plantillas_llm.json («dependencia», «sobreconfianza»),
nunca como números ni indicadores.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.linea_base.models import LineaBaseResultado
from app.modules.motor_retiro.models import EventoMotor

log = logging.getLogger("app.motor")


def banderas_iniciales(db: Session, usuario_id: int) -> dict:
    """`linea_base_resultados.banderas_iniciales` ({r9, r11, ajuste_ns_3_1}); vacío si no hay diagnóstico."""
    valor = db.scalar(select(LineaBaseResultado.banderas_iniciales).where(LineaBaseResultado.usuario_id == usuario_id))
    return valor if isinstance(valor, dict) else {}


def _bandera(db: Session, usuario_id: int, regla: str, clave: str) -> bool:
    datos = banderas_iniciales(db, usuario_id).get(regla)
    return bool(datos.get(clave)) if isinstance(datos, dict) else False


def dependencia_inicial(db: Session, usuario_id: int) -> bool:
    """R9: la línea base cumplió al menos 2 de las 3 señales (1.6, 3.2, 3.6)."""
    return _bandera(db, usuario_id, "r9", "riesgo")


def sobreconfianza_inicial(db: Session, usuario_id: int) -> bool:
    """R11: la línea base marcó al menos 2 errores con confianza 4 o 5."""
    return _bandera(db, usuario_id, "r11", "sobreconfianza")


def registrar_activacion(
    db: Session, usuario_id: int, concepto_id: int | None, sesion_id: int | None, regla: str, detalle: str,
    indicadores: dict | None = None, ns: int | None = None,
) -> bool:
    """Deja en eventos_motor una activación de R9, R10 o R11 (el NS no cambia: resultado «mantiene»).
    Mejor esfuerzo: si falla no rompe al estudiante; devuelve si quedó guardada."""
    try:
        db.add(
            EventoMotor(
                usuario_id=usuario_id, concepto_id=concepto_id, sesion_id=sesion_id, regla=regla, ns_antes=ns,
                ns_despues=ns, resultado="mantiene", indicadores=indicadores, detalle=detalle[:500],
            )
        )
        db.commit()
        return True
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo registrar la activación de %s (sesión %s)", regla, sesion_id)
        return False


def ya_registrada(db: Session, usuario_id: int, sesion_id: int, regla: str) -> bool:
    """¿Ya hay una activación de `regla` en esta sesión? (R9 y R11 se registran una vez por desafío)."""
    return (
        db.scalar(
            select(EventoMotor.id).where(
                EventoMotor.usuario_id == usuario_id, EventoMotor.sesion_id == sesion_id, EventoMotor.regla == regla
            ).limit(1)
        )
        is not None
    )
