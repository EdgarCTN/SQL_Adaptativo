"""Motor de reglas (versión mínima: R5, R1 y R4). Se invoca al cerrar un desafío (resuelto o abandonado).

Nunca rompe el cierre: ante cualquier fallo (reglas.json ilegible, error de base, etc.) mantiene el NS,
registra el error en eventos_motor y devuelve None (CU04 EX2).
"""
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.analitica.servicio import registrar_historico
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.contexto import construir_contexto
from app.modules.motor_retiro.evaluador import evaluar
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO, NivelSoporteService

log = logging.getLogger("app.motor")


@dataclass(frozen=True)
class AjusteNivel:
    concepto: str  # nombre del concepto
    ns_anterior: int
    ns_nuevo: int
    motivo: str  # texto para el estudiante (mensajes_fijos.json)


def _texto_estudiante(clave: str | None, concepto: str, ns_anterior: int, ns_nuevo: int) -> str:
    try:
        texto = cargar_mensajes_fijos()["mensajes"][clave]["texto"] if clave else None
    except (KeyError, OSError, ValueError, TypeError):
        texto = None
    if texto:
        return texto.replace("{{concepto}}", concepto)
    return f"Tu nivel de ayuda en {concepto} pasó de {ns_anterior} a {ns_nuevo}."  # provisional: sin mensaje fijo


def _registrar_error(db: Session, sesion_id: int | None, usuario_id: int | None, error: Exception) -> None:
    """Mejor esfuerzo: deja constancia del fallo en una transacción nueva."""
    try:
        sesion = db.get(SesionDesafio, sesion_id) if sesion_id else None
        desafio = db.get(Desafio, sesion.desafio_id) if sesion else None
        concepto_id = desafio.concepto_id if desafio else None
        ns = NivelSoporteService(db).obtener(usuario_id, concepto_id) if concepto_id and usuario_id else None
        db.add(
            EventoMotor(
                usuario_id=usuario_id,
                concepto_id=concepto_id,
                sesion_id=sesion_id,
                regla=None,
                ns_antes=ns,
                ns_despues=ns,  # el NS se mantiene
                resultado="error",
                indicadores=None,
                detalle=f"{type(error).__name__}: {error}"[:500],
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo registrar el error del motor")


def _guardar_historico(db: Session, usuario_id: int, concepto_id: int, sesion_id: int, indicadores: dict, ns: int) -> None:
    """Una fila en indicadores_historicos por cierre. Si falla, el cierre y el ajuste de NS no se tocan."""
    try:
        registrar_historico(db, usuario_id, concepto_id, sesion_id, indicadores, ns)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo guardar el indicador histórico (sesión %s)", sesion_id)


def cerrar_desafio(db: Session, sesion: SesionDesafio, reglas: dict | None = None) -> AjusteNivel | None:
    sesion_id, usuario_id = sesion.id, sesion.usuario_id
    try:
        reglas = reglas or cargar_reglas()
        desafio = db.get(Desafio, sesion.desafio_id)
        concepto = db.get(Concepto, desafio.concepto_id)
        ctx = construir_contexto(db, sesion, desafio, concepto, reglas)
        ev = evaluar(ctx)

        ns_antes, ns_nuevo = ctx.ns_actual, ev.ns_nuevo
        cambio = ns_nuevo != ns_antes
        fila = db.scalar(
            select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto.id)
        )
        ahora = ahora_utc()
        if cambio:
            if fila is None:  # sin registro (NS por defecto): se crea al primer cambio
                fila = NivelSoporte(usuario_id=usuario_id, concepto_id=concepto.id, ns=ns_nuevo, ns_maximo_historico=ns_nuevo)
                db.add(fila)
            fila.ns = ns_nuevo
            fila.ultimo_cambio_en = ahora  # reinicia la ventana
            fila.desafios_desde_cambio = 0
            fila.ns_maximo_historico = max(int(fila.ns_maximo_historico or 0), ns_antes, ns_nuevo)
            db.add(
                HistorialNivel(
                    usuario_id=usuario_id, concepto_id=concepto.id, ns_anterior=ns_antes, ns_nuevo=ns_nuevo,
                    regla=ev.regla, motivo=ev.motivo, creado_en=ahora,
                )
            )
        elif fila is not None:
            fila.desafios_desde_cambio = ctx.desafios_desde_cambio
        db.add(
            EventoMotor(
                usuario_id=usuario_id, concepto_id=concepto.id, sesion_id=sesion_id, regla=ev.regla,
                ns_antes=ns_antes, ns_despues=ns_nuevo, resultado="cambio" if cambio else "mantiene",
                indicadores={**ctx.indicadores.como_dict(), "desafios_desde_cambio": ctx.desafios_desde_cambio,
                             "resultado_sesion": ctx.resultado_sesion},
                detalle=ev.motivo, creado_en=ahora,
            )
        )
        db.commit()
        _guardar_historico(db, usuario_id, concepto.id, sesion_id, ctx.indicadores.como_dict(), ns_nuevo)
        if not cambio:
            return None
        return AjusteNivel(concepto.nombre, ns_antes, ns_nuevo, _texto_estudiante(ev.clave_mensaje, concepto.nombre, ns_antes, ns_nuevo))
    except Exception as e:  # noqa: BLE001  (el cierre del desafío nunca se rompe)
        log.exception("Falló el motor de reglas (sesión %s): se mantiene el NS", sesion_id)
        db.rollback()
        _registrar_error(db, sesion_id, usuario_id, e)
        return None
