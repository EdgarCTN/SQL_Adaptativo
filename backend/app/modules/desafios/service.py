import logging
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.errores import ErrorApp
from app.core.reglas import cargar_reglas
from app.modules.auth.models import Usuario
from app.modules.asistencia.cierre import clasificar_cierre
from app.modules.asistencia.models import SolicitudAyuda
from app.modules.desafios import hooks
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import Omision
from app.modules.motor_retiro import verificacion as verificaciones
from app.modules.motor_retiro.motor import AjusteNivel, ResultadoMotor
from app.modules.motor_retiro.niveles import NivelSoporteService
from app.modules.desafios.sandbox import ErrorConfiguracionDesafio, evaluar_consulta

log = logging.getLogger("app.desafios")

DIFICULTADES = ("D1", "D2", "D3")
MSG_SIN_DESAFIOS = "Todavía no hay desafíos disponibles. Vuelve a intentarlo más tarde."
MSG_SIN_DESAFIOS_FILTRO = "No hay desafíos disponibles para ese concepto."
MSG_NO_DISPONIBLE = "Este desafío no está disponible por ahora. Puedes elegir otro de la lista."
MSG_NO_EN_CURSO = "Este desafío no está en curso. Inícialo para poder enviar consultas."
MSG_NO_ABANDONAR = "No tienes este desafío en curso, así que no hay nada que abandonar."
MSG_ERROR_GUARDADO = "No pudimos guardar tu intento. Inténtalo de nuevo en unos segundos."
MSG_DESAFIO_ROTO = "Este desafío no se puede evaluar en este momento. Inténtalo más tarde o elige otro."
MSG_ABANDONADO = "Abandonaste el desafío. Puedes volver a intentarlo cuando quieras."
MSG_NO_OMITIR = "No tienes este desafío en curso, así que no hay nada que omitir."
MSG_OMITIDO = "Omitiste el desafío. No cuenta como resuelto ni como fallo."


def _concepto_out(c: Concepto) -> dict:
    return {"codigo": c.codigo, "nombre": c.nombre}


def _segundos(inicio: datetime, fin: datetime) -> int:
    return max(0, round((fin - inicio).total_seconds()))


def _desafio_activo(db: Session, desafio_id: int) -> Desafio:
    d = db.get(Desafio, desafio_id)
    if d is None or not d.activo:
        raise ErrorApp(MSG_NO_DISPONIBLE, 404)  # EX2
    return d


def _sesion_en_curso(db: Session, usuario_id: int, desafio_id: int) -> SesionDesafio | None:
    return db.scalar(
        select(SesionDesafio).where(
            SesionDesafio.usuario_id == usuario_id,
            SesionDesafio.desafio_id == desafio_id,
            SesionDesafio.estado == "en_curso",
        )
    )


def _n_intentos(db: Session, sesion_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Intento).where(Intento.sesion_id == sesion_id)) or 0


def _estados_usuario(db: Session, usuario_id: int) -> dict[int, str]:
    """desafio_id -> 'resuelto' | 'en_curso' (los demás son 'sin_iniciar')."""
    estados: dict[int, str] = {}
    filas = db.execute(
        select(SesionDesafio.desafio_id, SesionDesafio.estado, SesionDesafio.resultado_cierre).where(
            SesionDesafio.usuario_id == usuario_id, SesionDesafio.estado.in_(("resuelto", "en_curso"))
        )
    )
    for desafio_id, estado, cierre in filas:
        if estado == "resuelto" and cierre == "NR":  # vio la solución completa: cuenta como no resuelto
            continue
        if estados.get(desafio_id) != "resuelto":
            estados[desafio_id] = estado
    return estados


# ---------- Lectura ----------
def listar(db: Session, usuario: Usuario, concepto: str | None) -> dict:
    activos = db.execute(
        select(Desafio, Concepto)
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .where(Desafio.activo.is_(True))
        .order_by(Concepto.id, Desafio.id)
    ).all()
    conceptos: dict[int, dict] = {}
    for _, c in activos:
        conceptos.setdefault(c.id, _concepto_out(c))
    codigo = (concepto or "").strip()
    estados = _estados_usuario(db, usuario.id)
    en_verificacion = verificaciones.ids_verificacion_pendiente(db, usuario.id)
    grupos = {d: [] for d in DIFICULTADES}
    total = 0
    for d, c in activos:
        if codigo and c.codigo != codigo:
            continue
        grupos[d.dificultad].append(
            {
                "id": d.id,
                "titulo": d.titulo,
                "concepto": _concepto_out(c),
                "dificultad": d.dificultad,
                "tiempo_referencia_seg": d.tiempo_referencia_seg,
                "estado": estados.get(d.id, "sin_iniciar"),
                "verificacion": d.id in en_verificacion,
            }
        )
        total += 1
    mensaje = None
    if total == 0:  # EX1
        mensaje = MSG_SIN_DESAFIOS_FILTRO if codigo and activos else MSG_SIN_DESAFIOS
    return {
        "total": total,
        "mensaje": mensaje,
        "conceptos": list(conceptos.values()),
        "grupos": [{"dificultad": k, "desafios": v} for k, v in grupos.items()],
    }


def detalle(db: Session, usuario: Usuario, desafio_id: int) -> dict:
    d = _desafio_activo(db, desafio_id)
    c = db.get(Concepto, d.concepto_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    estado = _estados_usuario(db, usuario.id).get(d.id, "sin_iniciar")
    return {
        "id": d.id,
        "titulo": d.titulo,
        "enunciado": d.enunciado,
        "recursos": list(d.recursos or []),
        "concepto": _concepto_out(c),
        "dificultad": d.dificultad,
        "esquema_sql": d.esquema_sql,
        "tiempo_referencia_seg": d.tiempo_referencia_seg,
        "estado": estado,
        "sesion_en_curso": (
            {"sesion_id": sesion.id, "inicio": sesion.inicio, "intentos_realizados": _n_intentos(db, sesion.id)}
            if sesion
            else None
        ),
        "verificacion": verificaciones.es_verificacion_pendiente(db, usuario.id, d.id),
    }


# ---------- Sesión ----------
def _respuesta_inicio(db: Session, sesion: SesionDesafio, reanudada: bool) -> dict:
    return {
        "sesion_id": sesion.id,
        "desafio_id": sesion.desafio_id,
        "estado": sesion.estado,
        "inicio": sesion.inicio,
        "reanudada": reanudada,
        "intentos_realizados": _n_intentos(db, sesion.id),
    }


def iniciar(db: Session, usuario: Usuario, desafio_id: int) -> dict:
    d = _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    if sesion:
        return _respuesta_inicio(db, sesion, True)
    sesion = SesionDesafio(usuario_id=usuario.id, desafio_id=d.id, inicio=ahora_utc(), estado="en_curso")
    db.add(sesion)
    try:
        db.commit()
    except IntegrityError:  # doble clic: otra petición creó la sesión primero
        db.rollback()
        sesion = _sesion_en_curso(db, usuario.id, d.id)
        if sesion is None:
            raise ErrorApp(MSG_ERROR_GUARDADO, 503)
        return _respuesta_inicio(db, sesion, True)
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo iniciar la sesión")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    return _respuesta_inicio(db, sesion, False)


def _cerrar(sesion: SesionDesafio, estado: str, resultado: str) -> None:
    sesion.fin = ahora_utc()
    sesion.estado = estado
    sesion.resultado_cierre = resultado
    if sesion.tiempo_activo_origen == "latidos":  # hubo latidos: se usa lo acumulado
        sesion.tiempo_activo_seg = max(0, sesion.tiempo_activo_seg or 0)
    else:  # sin latidos: fin - inicio, como antes
        sesion.tiempo_activo_seg = _segundos(sesion.inicio, sesion.fin)
        sesion.tiempo_activo_origen = "reloj"


def _hueco_max_seg() -> int | None:
    """Valor de reglas.json (PROVISIONAL). Si no se puede leer, los latidos no suman y rige fin - inicio."""
    try:
        return int(cargar_reglas()["tiempo_activo"]["hueco_max_seg"])
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("No se pudo leer tiempo_activo.hueco_max_seg; el latido no suma tiempo")
        return None


def registrar_latido(db: Session, usuario: Usuario, desafio_id: int) -> dict:
    """Suma los segundos desde el latido anterior (o desde el inicio) si el hueco no supera el máximo."""
    sesion = _sesion_en_curso(db, usuario.id, desafio_id)
    if sesion is None:
        raise ErrorApp(MSG_NO_EN_CURSO, 409)
    hueco_max = _hueco_max_seg()
    if hueco_max is None:  # sin umbral no se activa el modo latidos: la sesión seguirá midiéndose con el reloj
        return {"ok": True, "tiempo_activo_seg": sesion.tiempo_activo_seg or 0}
    ahora = ahora_utc()
    referencia = sesion.ultimo_latido_en or sesion.inicio
    hueco = _segundos(referencia, ahora)
    if hueco <= hueco_max:
        sesion.tiempo_activo_seg = (sesion.tiempo_activo_seg or 0) + hueco
    elif sesion.tiempo_activo_seg is None:
        sesion.tiempo_activo_seg = 0
    sesion.ultimo_latido_en = ahora
    sesion.tiempo_activo_origen = "latidos"
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo guardar el latido")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    return {"ok": True, "tiempo_activo_seg": sesion.tiempo_activo_seg}


def _notificar_cierre(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """El cierre ya está guardado: un fallo del hook nunca debe romper la respuesta. Devuelve lo que decidió el motor."""
    try:
        r = hooks.al_cerrar_desafio(db, sesion)
    except Exception:  # noqa: BLE001
        log.exception("Falló al_cerrar_desafio (sesión %s); el cierre se conserva", sesion.id)
        db.rollback()
        return ResultadoMotor()
    if isinstance(r, AjusteNivel):  # hook con la firma de las entregas anteriores
        return ResultadoMotor(ajuste=r)
    return r if isinstance(r, ResultadoMotor) else ResultadoMotor()


def registrar_intento(db: Session, usuario: Usuario, desafio_id: int, codigo: str) -> dict:
    d = _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    if sesion is None:
        raise ErrorApp(MSG_NO_EN_CURSO, 409)
    try:
        res = evaluar_consulta(d.sandbox_setup_sql, d.solucion_referencia, codigo)
    except ErrorConfiguracionDesafio:
        log.exception("El desafío %s tiene un setup o una solución inválidos", d.id)
        raise ErrorApp(MSG_DESAFIO_ROTO, 503)

    resultado_cierre = None
    if res.correcto:  # Tabla 3: SA, CP, CE o NR según las ayudas recibidas y el NS vigente
        tipos = list(
            db.scalars(select(SolicitudAyuda.tipo_ayuda).where(SolicitudAyuda.sesion_id == sesion.id).order_by(SolicitudAyuda.id))
        )
        resultado_cierre = clasificar_cierre(tipos, NivelSoporteService(db).obtener(usuario.id, d.concepto_id))

    intento = None
    for _ in range(3):  # reintenta si otro envío simultáneo tomó el mismo número
        numero = (db.scalar(select(func.max(Intento.numero)).where(Intento.sesion_id == sesion.id)) or 0) + 1
        intento = Intento(
            sesion_id=sesion.id,
            numero=numero,
            codigo=codigo,
            correcto=res.correcto,
            resultado_obtenido=res.para_guardar(),
            creado_en=ahora_utc(),
        )
        db.add(intento)
        if res.correcto:
            _cerrar(sesion, "resuelto", resultado_cierre)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            db.refresh(sesion)
            if sesion.estado != "en_curso":
                raise ErrorApp(MSG_NO_EN_CURSO, 409)
            intento = None
        except SQLAlchemyError:
            db.rollback()
            log.exception("No se pudo guardar el intento")
            raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    if intento is None:
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    r = _notificar_cierre(db, sesion) if res.correcto else ResultadoMotor()
    return {
        "numero": intento.numero,
        "correcto": res.correcto,
        "tipo_resultado": res.tipo,
        "mensaje": res.mensaje,
        "detalle_tecnico": res.detalle_tecnico,
        "columnas": res.columnas,
        "filas": res.filas,
        "total_filas": res.total_filas,
        "truncado": res.truncado,
        "desafio_resuelto": res.correcto,
        "estado_sesion": sesion.estado,
        "resultado_cierre": sesion.resultado_cierre,
        "tiempo_activo_seg": sesion.tiempo_activo_seg,
        "creado_en": intento.creado_en,
        "ajuste_nivel": asdict(r.ajuste) if r.ajuste else None,
        "mensajes": [asdict(m) for m in r.mensajes],
    }


def abandonar(db: Session, usuario: Usuario, desafio_id: int) -> dict:
    _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, desafio_id)
    if sesion is None:
        raise ErrorApp(MSG_NO_ABANDONAR, 409)
    _cerrar(sesion, "abandonado", "NR")
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo abandonar el desafío")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    r = _notificar_cierre(db, sesion)
    return {
        "estado": sesion.estado,
        "resultado_cierre": sesion.resultado_cierre,
        "tiempo_activo_seg": sesion.tiempo_activo_seg,
        "mensaje": MSG_ABANDONADO,
        "ajuste_nivel": asdict(r.ajuste) if r.ajuste else None,
        "mensajes": [asdict(m) for m in r.mensajes],
    }


def _notificar_omision(db: Session, sesion: SesionDesafio) -> ResultadoMotor:
    """La omisión ya está guardada: un fallo del motor nunca debe romper la respuesta."""
    try:
        resultado = hooks.al_omitir_desafio(db, sesion)
    except Exception:  # noqa: BLE001
        log.exception("Falló al_omitir_desafio (sesión %s); la omisión se conserva", sesion.id)
        db.rollback()
        return ResultadoMotor()
    return resultado if isinstance(resultado, ResultadoMotor) else ResultadoMotor()


def omitir(db: Session, usuario: Usuario, desafio_id: int, motivo: str) -> dict:
    """Cierra la sesión como omitida y guarda el motivo. No cuenta como resuelto ni como fallo y no entra en la
    ventana; el motor aplica R8 («Muy difícil») o R7 («Muy fácil»)."""
    d = _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    if sesion is None:
        raise ErrorApp(MSG_NO_OMITIR, 409)
    _cerrar(sesion, "omitido", None)
    db.add(
        Omision(
            usuario_id=usuario.id, concepto_id=d.concepto_id, desafio_id=d.id, sesion_id=sesion.id,
            motivo=motivo, origen="desafio",
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo omitir el desafío")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    r = _notificar_omision(db, sesion)
    texto_verificacion = next((m.texto for m in r.mensajes if m.tipo == "verificacion"), "")
    return {
        "estado": sesion.estado,
        "motivo": motivo,
        "mensaje": MSG_OMITIDO,
        "ajuste_nivel": asdict(r.ajuste) if r.ajuste else None,
        "sugerido": asdict(r.sugerido) if r.sugerido else None,
        "verificacion": {**asdict(r.verificacion), "mensaje": texto_verificacion} if r.verificacion else None,
        "mensajes": [asdict(m) for m in r.mensajes],
    }
