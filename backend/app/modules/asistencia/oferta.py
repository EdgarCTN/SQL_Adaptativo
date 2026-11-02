"""Oferta de ayuda dentro del desafío (Matriz, Tabla 11) según la preferencia 3.3 de R13.

Tras un envío fallido, con ≥ 2 fallos o TR del desafío en curso ≥ 1.5 y NS ≥ 1:
- `a_solicitud`: no se ofrece nada (solo está el botón «Pedir ayuda»).
- `ofrecer`: la respuesta del intento incluye la tarjeta «¿Quieres una pista?»; el estudiante decide.
- `mostrar_sola`: la ayuda se pide automáticamente y se marca como mostrada sola (no cuenta para UA ni para R9).
En NS 0 no hay oferta. La ayuda que se ofrece es la del NS vigente, con los mínimos de AY3 y AY4 (y R9).

PROVISIONAL (Tabla 11 no lo define): (1) no hay oferta en un desafío de verificación (R7); (2) con una ayuda ya entregada
solo se vuelve a ofrecer tras ≥ 1 fallo nuevo; (3) nunca se ofrece ni se muestra sola AY4: la solución completa solo se
entrega si el estudiante la pide; (4) `mostrar_sola` muestra sola únicamente la primera ayuda del desafío, las siguientes
se ofrecen; (5) el TR se mide con el tiempo activo de la sesión (latidos) o, sin latidos, con el reloj.
Nunca lanza: ante cualquier fallo no hay oferta y el intento se responde igual.
"""
import logging

from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.asistencia import service
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.asistencia.decision import decidir_ayuda
from app.modules.asistencia.llm.base import LLMProvider
from app.modules.asistencia.preferencias import preferencia_ayuda
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Desafio, SesionDesafio
from app.modules.motor_retiro import verificacion as verificaciones
from app.modules.motor_retiro.niveles import NivelSoporteService

log = logging.getLogger("app.ayuda")

MOTIVO_FALLOS, MOTIVO_TIEMPO = "fallos", "tiempo"


def motivo_de_oferta(ns: int, fallos: int, tr: float | None, cfg: dict) -> str | None:
    """Función pura. `cfg` = reglas.json «ayuda_en_desafio». None si no corresponde ofrecer."""
    if ns < int(cfg["oferta_ns_minimo"]):
        return None
    if fallos >= int(cfg["oferta_fallos_minimos"]):
        return MOTIVO_FALLOS
    if tr is not None and tr >= float(cfg["oferta_tr_minimo"]):
        return MOTIVO_TIEMPO
    return None


def tr_en_curso(sesion: SesionDesafio, desafio: Desafio, ahora=None) -> float | None:
    """Tiempo activo del desafío en curso ÷ tiempo de referencia (con latidos usa lo acumulado; sin latidos, el reloj)."""
    if not desafio.tiempo_referencia_seg:
        return None
    if sesion.tiempo_activo_origen == "latidos":
        activo = float(sesion.tiempo_activo_seg or 0)
    else:
        activo = max(0.0, ((ahora or ahora_utc()) - sesion.inicio).total_seconds())
    return activo / desafio.tiempo_referencia_seg


def _tarjeta(modo: str, motivo: str, tipo: str, ayuda: dict | None = None) -> dict:
    mensajes = cargar_mensajes_fijos()["mensajes"]
    if modo == "mostrar_sola":
        fijo = mensajes.get("ayuda_mostrada_sola", {})
        return {"modo": modo, "motivo": motivo, "tipo_ayuda": tipo, "texto": fijo.get("texto") or "", "ayuda": ayuda}
    fijo = mensajes.get("oferta_ayuda", {})
    return {
        "modo": modo, "motivo": motivo, "tipo_ayuda": tipo, "texto": fijo.get("texto") or "¿Quieres una pista?",
        "boton": fijo.get("boton"), "boton_rechazo": fijo.get("boton_rechazo"), "ayuda": None,
    }


def evaluar_oferta(
    db: Session, usuario: Usuario, desafio: Desafio, sesion: SesionDesafio, proveedor: LLMProvider | None,
    reglas: dict | None = None,
) -> dict | None:
    try:
        reglas = reglas or cargar_reglas()
        cfg = reglas["ayuda_en_desafio"]
        if sesion.estado != "en_curso":
            return None
        ns = NivelSoporteService(db).obtener(usuario.id, desafio.concepto_id)
        if ns < int(cfg["oferta_ns_minimo"]):
            return None
        modo = preferencia_ayuda(db, usuario.id)
        if modo == "a_solicitud" or verificaciones.es_verificacion_pendiente(db, usuario.id, desafio.id):
            return None
        est = service.estado_ayuda(db, sesion)
        motivo = motivo_de_oferta(ns, est.fallos, tr_en_curso(sesion, desafio), cfg)
        if motivo is None or (est.previas and est.desde_ultima < 1):
            return None
        dep = service.dependencia_de(db, usuario.id, desafio.concepto_id)
        decision = decidir_ayuda(ns, est.fallos, est.tipos_previos, est.desde_ultima, reglas, bool(dep and dep.activa))
        if decision.tipo is None or decision.tipo == "AY4":
            return None
        if modo == "mostrar_sola" and not est.previas and proveedor is not None:
            try:
                ayuda = service.solicitar_ayuda(db, usuario, desafio.id, None, proveedor, mostrada_sola=True)
                if ayuda.get("solicitud_id"):
                    return _tarjeta("mostrar_sola", motivo, ayuda["tipo_ayuda"], ayuda)
            except Exception:  # noqa: BLE001  (si no se pudo mostrar sola, se ofrece)
                db.rollback()
                log.exception("No se pudo mostrar la ayuda sola (sesión %s)", sesion.id)
        return _tarjeta("ofrecer", motivo, decision.tipo)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Falló la oferta de ayuda (sesión %s): sin oferta", sesion.id)
        return None
