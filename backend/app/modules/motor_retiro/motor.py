"""Motor de reglas (R6, R8, R7, R5, R2, R1, R4; completo desde la entrega 5). Se invoca al cerrar un desafío (resuelto,
abandonado u omitido).

Nunca rompe el cierre: ante cualquier fallo (reglas.json ilegible, error de base, etc.) mantiene el NS,
registra el error en eventos_motor y devuelve un resultado vacío (CU04 EX2).
"""
import logging
from dataclasses import dataclass, field
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.analitica.servicio import registrar_historico
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte, Omision
from app.modules.motor_retiro import mensajes, omisiones, verificacion
from app.modules.motor_retiro.contexto import construir_contexto
from app.modules.motor_retiro.evaluador import evaluar
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from app.modules.motor_retiro.niveles import NivelSoporteService
from app.modules.motor_retiro.reglas.base import ACCION_ESTANCAMIENTO, ACCION_SUGERIR, ACCION_VERIFICACION
from app.modules.motor_retiro.verificacion import VerificacionAsignada

log = logging.getLogger("app.motor")


@dataclass(frozen=True)
class AjusteNivel:
    concepto: str  # nombre del concepto
    ns_anterior: int
    ns_nuevo: int
    motivo: str  # texto para el estudiante (mensajes_fijos.json)


@dataclass(frozen=True)
class DesafioSugerido:
    id: int
    titulo: str
    dificultad: str


@dataclass(frozen=True)
class ResultadoMotor:
    """Lo que el motor decidió al cerrar un desafío. Todo vacío si no cambió nada o si el motor falló."""

    ajuste: AjusteNivel | None = None
    sugerido: DesafioSugerido | None = None  # R8
    verificacion: VerificacionAsignada | None = None  # R7 (el campo se llama como el módulo: por eso se importa la clase aparte)
    mensajes: tuple[MensajeEstudiante, ...] = field(default_factory=tuple)


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


def _completar_verificacion(db: Session, sesion: SesionDesafio) -> None:
    """Mejor esfuerzo, ya guardado el cierre: marca como completada la verificación de este desafío, si la había."""
    try:
        verificacion.completar_si_corresponde(db, sesion)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo completar la verificación (sesión %s)", sesion.id)


def _motivo_omision(db: Session, sesion_id: int) -> str | None:
    return db.scalar(select(Omision.motivo).where(Omision.sesion_id == sesion_id).order_by(Omision.id.desc()).limit(1))


def _procesar(db: Session, sesion: SesionDesafio, reglas: dict | None, omision_motivo: str | None) -> ResultadoMotor:
    sesion_id, usuario_id = sesion.id, sesion.usuario_id
    try:
        reglas = reglas or cargar_reglas()
        desafio = db.get(Desafio, sesion.desafio_id)
        concepto = db.get(Concepto, desafio.concepto_id)
        ctx = construir_contexto(db, sesion, desafio, concepto, reglas, omision_motivo)
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

        # Acciones que necesitan la base de datos (las reglas solo deciden).
        sugerido = asignada = None
        detalle = ev.motivo
        if ev.accion == ACCION_SUGERIR:
            ref = omisiones.buscar_mas_basico(db, usuario_id, desafio.id)
            sugerido = DesafioSugerido(ref.id, ref.titulo, ref.dificultad) if ref else None
        elif ev.accion == ACCION_VERIFICACION:
            asignada = verificacion.asignar(db, usuario_id, concepto.id, "desafio", omitido_id=desafio.id)
            if asignada is None:
                detalle += " (sin desafío disponible: el contador no se reinicia)"

        indicadores = {**ctx.indicadores.como_dict(), "desafios_desde_cambio": ctx.desafios_desde_cambio,
                       "resultado_sesion": ctx.resultado_sesion, **ev.extra}  # extra: p. ej. r6_condicion, prerrequisito
        if omision_motivo is not None:
            indicadores.update(
                omision=omision_motivo, omisiones_muy_facil=ctx.omisiones_muy_facil,
                omisiones_muy_dificil_seguidas=ctx.omisiones_muy_dificil_seguidas,
                sugerido_id=sugerido.id if sugerido else None, verificacion_id=asignada.desafio_id if asignada else None,
            )
        db.add(
            EventoMotor(
                usuario_id=usuario_id, concepto_id=concepto.id, sesion_id=sesion_id, regla=ev.regla,
                ns_antes=ns_antes, ns_despues=ns_nuevo, resultado="cambio" if cambio else "mantiene",
                indicadores=indicadores, detalle=detalle, creado_en=ahora,
            )
        )
        db.commit()
        if omision_motivo is None:  # una omisión no entra en la ventana: tampoco deja fila en el histórico de indicadores
            _guardar_historico(db, usuario_id, concepto.id, sesion_id, ctx.indicadores.como_dict(), ns_nuevo)
        _completar_verificacion(db, sesion)

        ajuste = None
        lista: list[MensajeEstudiante] = []
        if cambio:
            texto = mensajes.texto_cambio_ns(ev.clave_mensaje, concepto.nombre, ns_antes, ns_nuevo)
            ajuste = AjusteNivel(concepto.nombre, ns_antes, ns_nuevo, texto)
            lista.append(MensajeEstudiante(ev.clave_mensaje or "cambio_ns", mensajes.TIPO_REFUERZO if ns_nuevo > ns_antes else mensajes.TIPO_RETIRO, texto))
        if sugerido is not None:
            m = mensajes.mensaje("sugerencia_mas_basico", concepto=concepto.nombre, desafio=sugerido.titulo)
            if m:
                lista.append(m)
        if asignada is not None:
            m = mensajes.mensaje(ev.clave_mensaje or "verificacion", concepto=concepto.nombre)
            if m:
                lista.append(m)
        if ev.accion == ACCION_ESTANCAMIENTO:  # R6: el NS no cambia; deriva o manda a practicar el concepto previo
            previo = ev.clave_mensaje == "estancamiento_previo_sin_dominar" and ctx.prerrequisito_codigo is not None
            m = mensajes.mensaje(
                ev.clave_mensaje,
                enlace=f"/desafios?concepto={quote(ctx.prerrequisito_codigo, safe='')}" if previo else None,
                concepto=concepto.nombre,
                concepto_previo=ctx.prerrequisito_nombre or "",
            )
            if m:
                lista.append(m)
        return ResultadoMotor(ajuste, sugerido, asignada, tuple(lista))
    except Exception as e:  # noqa: BLE001  (el cierre del desafío nunca se rompe)
        log.exception("Falló el motor de reglas (sesión %s): se mantiene el NS", sesion_id)
        db.rollback()
        _registrar_error(db, sesion_id, usuario_id, e)
        return ResultadoMotor()


def cerrar_desafio_con_mensajes(db: Session, sesion: SesionDesafio, reglas: dict | None = None) -> ResultadoMotor:
    """Cierre por resolución o abandono: ajuste de NS y mensajes al estudiante (R6 añade el suyo sin cambiar el NS)."""
    return _procesar(db, sesion, reglas, None)


def cerrar_desafio(db: Session, sesion: SesionDesafio, reglas: dict | None = None) -> AjusteNivel | None:
    """Cierre por resolución o abandono. Conserva la firma de las entregas anteriores."""
    return cerrar_desafio_con_mensajes(db, sesion, reglas).ajuste


def cerrar_omision(db: Session, sesion: SesionDesafio, reglas: dict | None = None) -> ResultadoMotor:
    """Cierre por omisión (R8, R7). La sesión ya está guardada como `omitido` y su fila en `omisiones` también."""
    motivo = _motivo_omision(db, sesion.id)
    if motivo is None:  # sin fila de omisión no hay nada que evaluar
        log.error("La sesión %s está omitida pero no tiene fila en omisiones", sesion.id)
        return ResultadoMotor()
    return _procesar(db, sesion, reglas, motivo)
