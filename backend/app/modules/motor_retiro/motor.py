"""Motor de reglas (R6, R8, R7, R5, R2, R1, R4; completo desde la entrega 5; R3 como condicionante desde la 6; la
preferencia 3.4 (R13) decide desde la 7 si un retiro se aplica, espera al estudiante o se omite; R11 (sobreconfianza)
condiciona a R1 desde la 8). Se invoca
al cerrar un desafío (resuelto, abandonado u omitido). Entrega 6: `iniciar_desafio` (R12, al iniciar un desafío) y
`evaluar_inactividad` (R14, al iniciar sesión).

Nunca rompe el cierre: ante cualquier fallo (reglas.json ilegible, error de base, etc.) mantiene el NS,
registra el error en eventos_motor y devuelve un resultado vacío (CU04 EX2).
"""
import logging
from dataclasses import dataclass, field
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.analitica.extractores import sesiones_cerradas_df
from app.modules.analitica.servicio import registrar_historico
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte, Omision
from app.modules.motor_retiro import cambio_dificultad, inactividad, mensajes, omisiones, retiro_diferido, verificacion
from app.modules.motor_retiro.contexto import construir_contexto
from app.modules.motor_retiro.evaluador import evaluar
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO, NivelSoporteService
from app.modules.motor_retiro.reglas.base import ACCION_ESTANCAMIENTO, ACCION_SUGERIR, ACCION_VERIFICACION
from app.modules.motor_retiro.reglas.r1_retiro_estandar import R1RetiroEstandar
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


def _guardar_cambio_ns(
    db: Session, fila: NivelSoporte | None, usuario_id: int, concepto_id: int, ns_antes: int, ns_nuevo: int,
    regla: str, motivo: str, ahora, es_retiro: bool,
) -> NivelSoporte:
    """Aplica un cambio de NS (sin confirmar): fila de niveles_soporte (se crea si falta), ventana reiniciada y fila de
    historial_niveles. `es_retiro` guarda el NS previo para R3; cualquier otro cambio lo borra."""
    if fila is None:  # sin registro (NS por defecto): se crea al primer cambio
        fila = NivelSoporte(usuario_id=usuario_id, concepto_id=concepto_id, ns=ns_nuevo, ns_maximo_historico=ns_nuevo)
        db.add(fila)
    fila.ns = ns_nuevo
    fila.ultimo_cambio_en = ahora  # reinicia la ventana
    fila.desafios_desde_cambio = 0
    fila.ns_maximo_historico = max(int(fila.ns_maximo_historico or 0), ns_antes, ns_nuevo)
    fila.ns_previo_retiro = ns_antes if es_retiro else None
    db.add(
        HistorialNivel(
            usuario_id=usuario_id, concepto_id=concepto_id, ns_anterior=ns_antes, ns_nuevo=ns_nuevo,
            regla=regla, motivo=motivo, creado_en=ahora,
        )
    )
    return fila


def _procesar(db: Session, sesion: SesionDesafio, reglas: dict | None, omision_motivo: str | None) -> ResultadoMotor:
    sesion_id, usuario_id = sesion.id, sesion.usuario_id
    try:
        reglas = reglas or cargar_reglas()
        desafio = db.get(Desafio, sesion.desafio_id)
        concepto = db.get(Concepto, desafio.concepto_id)
        ctx = construir_contexto(db, sesion, desafio, concepto, reglas, omision_motivo)
        ev = evaluar(ctx)
        # R11: R1 se habría aplicado de no ser por la sobreconfianza (quedó R4); se deja constancia más abajo.
        r11_bloqueo = omision_motivo is None and ev.regla == "R4" and R1RetiroEstandar.bloqueada_por_r11(ctx)

        ns_antes, ns_nuevo = ctx.ns_actual, ev.ns_nuevo
        cambio = ns_nuevo != ns_antes
        fila = db.scalar(
            select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto.id)
        )
        ahora = ahora_utc()
        retiros = [str(r) for r in reglas["recaida_y_pausas"]["reglas_que_cuentan_como_retiro"]]
        # R13 (pregunta 3.4): un retiro de R1 o R2 puede esperar al estudiante o no aplicarse; entonces el NS no cambia.
        diferido = None
        if cambio and omision_motivo is None and ev.regla in retiros and ns_nuevo < ns_antes:
            diferido = retiro_diferido.decidir(
                db, usuario_id, concepto.id, sesion_id, ev.regla, ns_antes, ns_nuevo, ev.motivo, ahora,
                ns_antes, ctx.pausa_retiros,
            )
            if diferido is not None:
                ns_nuevo, cambio = ns_antes, False
        if cambio:
            fila = _guardar_cambio_ns(
                db, fila, usuario_id, concepto.id, ns_antes, ns_nuevo, ev.regla, ev.motivo, ahora,
                es_retiro=ev.regla in retiros,
            )
        elif fila is not None:
            fila.desafios_desde_cambio = ctx.desafios_desde_cambio
        # Pausa de R1 y R2: R3 la inicia; cada desafío cerrado (no omitido) la gasta uno.
        if ev.pausa_retiros and fila is not None:
            fila.pausa_retiros_restante = ev.pausa_retiros
        elif omision_motivo is None and fila is not None and ctx.pausa_retiros > 0:
            fila.pausa_retiros_restante = ctx.pausa_retiros - 1

        # Acciones que necesitan la base de datos (las reglas solo deciden).
        sugerido = asignada = None
        detalle = diferido.detalle if diferido is not None else ev.motivo
        if ev.accion == ACCION_SUGERIR:
            ref = omisiones.buscar_mas_basico(db, usuario_id, desafio.id)
            sugerido = DesafioSugerido(ref.id, ref.titulo, ref.dificultad) if ref else None
        elif ev.accion == ACCION_VERIFICACION:
            asignada = verificacion.asignar(db, usuario_id, concepto.id, "desafio", omitido_id=desafio.id)
            if asignada is None:
                detalle += " (sin desafío disponible: el contador no se reinicia)"

        indicadores = {**ctx.indicadores.como_dict(), "desafios_desde_cambio": ctx.desafios_desde_cambio,
                       "resultado_sesion": ctx.resultado_sesion, "pausa_retiros": ctx.pausa_retiros,
                       **ev.extra}  # extra: p. ej. r6_condicion, prerrequisito
        if diferido is not None:
            indicadores["r13"] = {
                "preferencia_3_4": diferido.modo, "criterio_cumplido": ev.regla, "ns_propuesto": ev.ns_nuevo,
                "ajuste_id": diferido.ajuste.id if diferido.ajuste is not None else None,
                "mensaje": diferido.clave_mensaje,
            }
        if r11_bloqueo:
            n_sa = int(reglas["r11_sobreconfianza"]["desafios_sa_exigidos_para_retiro"])
            indicadores["r11"] = {"retiro_bloqueado": True, "desafios_sa_exigidos": n_sa}
            db.add(
                EventoMotor(
                    usuario_id=usuario_id, concepto_id=concepto.id, sesion_id=sesion_id, regla="R11", ns_antes=ns_antes,
                    ns_despues=ns_antes, resultado="mantiene", creado_en=ahora,
                    indicadores={"ultimos": [c.resultado for c in ctx.cierres_recientes[-n_sa:]], "desafios_sa_exigidos": n_sa},
                    detalle=f"R11 sobreconfianza: el criterio de R1 se cumple, pero se exigen los últimos {n_sa} desafíos en SA",
                )
            )
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
            tipo = mensajes.tipo_de(ev.clave_mensaje, mensajes.TIPO_REFUERZO if ns_nuevo > ns_antes else mensajes.TIPO_RETIRO)
            lista.append(MensajeEstudiante(ev.clave_mensaje or "cambio_ns", tipo, texto))
        if diferido is not None and diferido.nuevo and diferido.clave_mensaje:  # R13: aviso previo o pregunta
            m = mensajes.mensaje(diferido.clave_mensaje, ajuste_id=diferido.ajuste.id, concepto=concepto.nombre)
            if m:
                lista.append(m)
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


def iniciar_desafio(db: Session, sesion: SesionDesafio, reglas: dict | None = None) -> ResultadoMotor:
    """R12 Cambio de dificultad, al iniciar un desafío nuevo (la sesión ya está guardada). Nunca rompe el inicio: ante
    cualquier fallo no cambia nada y deja el error en eventos_motor. Solo deja evento cuando la regla corresponde."""
    sesion_id, usuario_id = sesion.id, sesion.usuario_id
    try:
        reglas = reglas or cargar_reglas()
        desafio = db.get(Desafio, sesion.desafio_id)
        concepto = db.get(Concepto, desafio.concepto_id)
        cerradas = sesiones_cerradas_df(db, usuario_id, concepto.id)
        mayor_cerrada = max(cerradas["dificultad"], key=cambio_dificultad.RANGO.get, default=None)
        en_curso = db.scalars(
            select(Desafio.dificultad)
            .join(SesionDesafio, SesionDesafio.desafio_id == Desafio.id)
            .where(
                SesionDesafio.usuario_id == usuario_id, Desafio.concepto_id == concepto.id,
                SesionDesafio.estado == "en_curso", SesionDesafio.id != sesion_id,
            )
        ).all()
        mayor_en_curso = max(en_curso, key=cambio_dificultad.RANGO.get, default=None)
        fila = db.scalar(
            select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto.id)
        )
        ns_antes = int(fila.ns) if fila is not None else NS_POR_DEFECTO
        decision = cambio_dificultad.evaluar_cambio_dificultad(
            ns_antes, desafio.dificultad, mayor_cerrada, mayor_en_curso, reglas
        )
        if decision is None:
            return ResultadoMotor()

        ahora = ahora_utc()
        if decision.cambia_ns:
            fila = _guardar_cambio_ns(
                db, fila, usuario_id, concepto.id, ns_antes, decision.ns_nuevo, "R12", decision.motivo, ahora, es_retiro=False
            )
        elif fila is None:  # la pausa necesita fila; sin cambio de NS la ventana no se reinicia (cuenta desde el registro)
            usuario = db.get(Usuario, usuario_id)
            fila = NivelSoporte(
                usuario_id=usuario_id, concepto_id=concepto.id, ns=ns_antes, ns_maximo_historico=ns_antes,
                ultimo_cambio_en=(usuario.creado_en if usuario is not None and usuario.creado_en else ahora),
            )
            db.add(fila)
        fila.pausa_retiros_restante = max(int(fila.pausa_retiros_restante or 0), decision.pausa_retiros)
        db.add(
            EventoMotor(
                usuario_id=usuario_id, concepto_id=concepto.id, sesion_id=sesion_id, regla="R12", ns_antes=ns_antes,
                ns_despues=decision.ns_nuevo, resultado="cambio" if decision.cambia_ns else "mantiene",
                indicadores={"dificultad": desafio.dificultad, "mayor_cerrada": mayor_cerrada,
                             "pausa_retiros": fila.pausa_retiros_restante},
                detalle=decision.motivo, creado_en=ahora,
            )
        )
        db.commit()
        if not decision.cambia_ns:
            return ResultadoMotor()
        texto = mensajes.texto_cambio_ns("cambio_dificultad", concepto.nombre, ns_antes, decision.ns_nuevo)
        ajuste = AjusteNivel(concepto.nombre, ns_antes, decision.ns_nuevo, texto)
        tipo = mensajes.tipo_de("cambio_dificultad", mensajes.TIPO_REFUERZO)
        return ResultadoMotor(ajuste, mensajes=(MensajeEstudiante("cambio_dificultad", tipo, texto),))
    except Exception as e:  # noqa: BLE001  (iniciar un desafío nunca se rompe)
        log.exception("Falló R12 (sesión %s): no se cambia nada", sesion_id)
        db.rollback()
        _registrar_error(db, sesion_id, usuario_id, e)
        return ResultadoMotor()


def evaluar_inactividad(
    db: Session, usuario_id: int, reglas: dict | None = None, ahora=None
) -> MensajeEstudiante | None:
    """R14 Inactividad, al iniciar sesión. Con ≥ r14_inactividad.dias días desde la última sesión de desafío, el NS de
    cada concepto con fila sube 1 sin superar ns_maximo_historico. Una sola vez por periodo de inactividad: si ya hay un
    evento R14 posterior a la última actividad no hace nada. Devuelve el mensaje de reenganche, o None si no subió nada.
    PROVISIONAL: con varios conceptos, un solo mensaje que los nombra. Puede lanzar excepciones: quien llama las captura."""
    reglas = reglas or cargar_reglas()
    ahora = ahora or ahora_utc()
    dias = int(reglas["r14_inactividad"]["dias"])
    inicio_max, fin_max = db.execute(
        select(func.max(SesionDesafio.inicio), func.max(SesionDesafio.fin)).where(SesionDesafio.usuario_id == usuario_id)
    ).one()
    fechas = [inactividad.a_utc(f) for f in (inicio_max, fin_max) if f is not None]
    ultima = max(fechas) if fechas else None
    if not inactividad.esta_inactivo(ultima, ahora, dias):
        return None
    previo = db.scalar(
        select(func.max(EventoMotor.creado_en)).where(EventoMotor.usuario_id == usuario_id, EventoMotor.regla == "R14")
    )
    if previo is not None and inactividad.a_utc(previo) > ultima:
        return None  # ya se aplicó en esta inactividad
    dias_inactivo = (inactividad.a_utc(ahora) - ultima).days
    indicadores = {"dias_inactivo": dias_inactivo, "ultima_actividad": ultima.isoformat()}
    cambiados: list[str] = []
    filas = db.scalars(
        select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id).order_by(NivelSoporte.concepto_id)
    ).all()
    for fila in filas:
        antes = int(fila.ns)
        nuevo = inactividad.ns_tras_inactividad(antes, int(fila.ns_maximo_historico))
        if nuevo == antes:
            continue
        motivo = f"R14 inactividad: {dias_inactivo} días sin actividad; NS {antes} → {nuevo} (máximo histórico {fila.ns_maximo_historico})"
        _guardar_cambio_ns(db, fila, usuario_id, fila.concepto_id, antes, nuevo, "R14", motivo, ahora, es_retiro=False)
        db.add(
            EventoMotor(
                usuario_id=usuario_id, concepto_id=fila.concepto_id, regla="R14", ns_antes=antes, ns_despues=nuevo,
                resultado="cambio", indicadores=indicadores, detalle=motivo, creado_en=ahora,
            )
        )
        cambiados.append(db.get(Concepto, fila.concepto_id).nombre)
    if not cambiados:  # deja constancia para no volver a evaluar en cada inicio de sesión
        db.add(
            EventoMotor(
                usuario_id=usuario_id, regla="R14", resultado="mantiene", indicadores=indicadores, creado_en=ahora,
                detalle=f"R14 inactividad: {dias_inactivo} días sin actividad, ningún concepto puede subir (máximo histórico)",
            )
        )
    db.commit()
    return mensajes.mensaje("reenganche", concepto=mensajes.unir_nombres(cambiados)) if cambiados else None
