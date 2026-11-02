"""R10 Ensayo y error (Matriz, Tabla 9, bloque 5). Actúa DENTRO del desafío, al registrar un envío fallido; no forma
parte de la secuencia de cierre y no bloquea la ayuda.

Condición: los últimos `envios_fallidos_seguidos` envíos de la sesión fallaron y entre cada par consecutivo pasaron menos
de `segundos_entre_envios_max` segundos. Acción: la respuesta del intento incluye la pregunta de reflexión (mensaje fijo
`ensayo_error`) y queda un evento R10 en eventos_motor.
PROVISIONAL: no se repite hasta que haya otros `envios_fallidos_seguidos` envíos nuevos desde la última activación.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import cargar_reglas
from app.modules.desafios.models import Desafio, Intento, SesionDesafio
from app.modules.motor_retiro import banderas, mensajes
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.motor_retiro.models import EventoMotor
from app.modules.motor_retiro.niveles import NivelSoporteService

log = logging.getLogger("app.motor")


def es_ensayo_error(envios: list[tuple[bool, datetime]], cfg: dict) -> bool:
    """`envios`: (correcto, creado_en) del más antiguo al más reciente. Función pura."""
    n = int(cfg["envios_fallidos_seguidos"])
    if len(envios) < n:
        return False
    ultimos = envios[-n:]
    if any(correcto for correcto, _ in ultimos):
        return False
    maximo = float(cfg["segundos_entre_envios_max"])
    return all((b[1] - a[1]).total_seconds() < maximo for a, b in zip(ultimos, ultimos[1:]))


def evaluar_r10(db: Session, sesion: SesionDesafio, desafio: Desafio, reglas: dict | None = None) -> MensajeEstudiante | None:
    """Se llama tras guardar un envío fallido. Nunca lanza: ante un fallo no hay reflexión y el intento sigue igual."""
    try:
        cfg = (reglas or cargar_reglas())["r10_ensayo_error"]
        n = int(cfg["envios_fallidos_seguidos"])
        filas = db.execute(
            select(Intento.numero, Intento.correcto, Intento.creado_en)
            .where(Intento.sesion_id == sesion.id)
            .order_by(Intento.numero.desc())
            .limit(n)
        ).all()
        filas = list(reversed(filas))
        if not es_ensayo_error([(bool(f.correcto), f.creado_en) for f in filas], cfg):
            return None
        ultimo = int(filas[-1].numero)
        previo = db.scalar(
            select(EventoMotor.indicadores)
            .where(EventoMotor.sesion_id == sesion.id, EventoMotor.regla == "R10")
            .order_by(EventoMotor.id.desc())
            .limit(1)
        )
        if isinstance(previo, dict) and ultimo - int(previo.get("envio", 0)) < n:
            return None  # ya se preguntó por estos envíos
        mensaje = mensajes.mensaje("ensayo_error")
        if mensaje is None:
            return None
        banderas.registrar_activacion(
            db, sesion.usuario_id, desafio.concepto_id, sesion.id, "R10",
            f"R10 ensayo y error: {n} envíos fallidos seguidos con menos de {cfg['segundos_entre_envios_max']} s entre ellos",
            {"envio": ultimo, "envios_fallidos_seguidos": n, "segundos_entre_envios_max": cfg["segundos_entre_envios_max"]},
            NivelSoporteService(db).obtener(sesion.usuario_id, desafio.concepto_id),
        )
        return mensaje
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Falló R10 (sesión %s): se sigue sin reflexión", sesion.id)
        return None
