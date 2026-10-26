import copy
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApp
from app.core.reglas import cargar_reglas
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto
from app.modules.linea_base.models import (
    Consentimiento,
    LineaBaseCuestionario,
    LineaBaseRespuesta,
    LineaBaseResultado,
    NivelSoporte,
    Omision,
)
from app.modules.linea_base.calculo import calcular_linea_base
from app.modules.linea_base.schemas import RespuestaIn, RespuestasIn
from app.modules.motor_retiro import mensajes as mensajes_motor
from app.modules.motor_retiro import verificacion as verificaciones

log = logging.getLogger("app.linea_base")

VERSION_CONSENTIMIENTO = "1.0"  # versión vigente del texto de consentimiento (el texto lo muestra el frontend)

MSG_SIN_CONSENTIMIENTO = "El consentimiento es necesario para completar el diagnóstico inicial."
MSG_NO_ACEPTADO = "El consentimiento es necesario para completar el diagnóstico inicial. No guardamos nada."
MSG_NO_DISPONIBLE = "El cuestionario no puede presentarse en este momento. Inténtalo de nuevo más tarde."
MSG_YA_COMPLETADO = "Ya completaste el diagnóstico inicial."
MSG_ERROR_GUARDADO = (
    "No fue posible completar el diagnóstico en este momento. "
    "Tus respuestas siguen en pantalla: inténtalo de nuevo en unos minutos."
)


# ---------- Consentimiento ----------
def _consentimiento_vigente(db: Session, usuario: Usuario) -> Consentimiento | None:
    return db.scalar(
        select(Consentimiento).where(
            Consentimiento.usuario_id == usuario.id, Consentimiento.version == VERSION_CONSENTIMIENTO
        )
    )


def tiene_consentimiento(db: Session, usuario: Usuario) -> bool:
    return _consentimiento_vigente(db, usuario) is not None


def registrar_consentimiento(db: Session, usuario: Usuario, acepta: bool) -> dict:
    """Si no acepta, no se guarda nada."""
    if not acepta:
        return {"aceptado": False, "mensaje": MSG_NO_ACEPTADO}
    actual = _consentimiento_vigente(db, usuario)
    if actual is None:
        actual = Consentimiento(usuario_id=usuario.id, version=VERSION_CONSENTIMIENTO)
        db.add(actual)
        try:
            db.commit()
        except IntegrityError:  # doble clic: ya existe
            db.rollback()
            actual = _consentimiento_vigente(db, usuario)
        except SQLAlchemyError:
            db.rollback()
            log.exception("No se pudo guardar el consentimiento")
            raise ErrorApp("No pudimos registrar tu consentimiento. Inténtalo de nuevo.", 503)
    return {
        "aceptado": True,
        "version": actual.version,
        "aceptado_en": actual.aceptado_en,
        "mensaje": "Consentimiento registrado.",
    }


# ---------- Cuestionario ----------
def cuestionario_activo(db: Session) -> LineaBaseCuestionario | None:
    return db.scalar(
        select(LineaBaseCuestionario)
        .where(LineaBaseCuestionario.activo.is_(True))
        .order_by(LineaBaseCuestionario.version.desc())
        .limit(1)
    )


def quitar_clave(obj: Any, clave: str = "correcta") -> Any:
    """Copia profunda sin la clave indicada en ningún nivel."""
    if isinstance(obj, dict):
        return {k: quitar_clave(v, clave) for k, v in obj.items() if k != clave}
    if isinstance(obj, list):
        return [quitar_clave(v, clave) for v in obj]
    return copy.deepcopy(obj)


def estado(db: Session, usuario: Usuario) -> dict:
    cuestionario = cuestionario_activo(db)
    consentido = tiene_consentimiento(db, usuario)
    if usuario.linea_base_completada:
        paso = "completado"
    elif not consentido:
        paso = "consentimiento"
    elif cuestionario is None:
        paso = "no_disponible"
    else:
        paso = "cuestionario"
    return {
        "linea_base_completada": usuario.linea_base_completada,
        "consentimiento_aceptado": consentido,
        "version_consentimiento": VERSION_CONSENTIMIENTO,
        "cuestionario_disponible": cuestionario is not None,
        "cuestionario_id": cuestionario.id if cuestionario else None,
        "siguiente_paso": paso,
    }


def _exigir_puede_responder(db: Session, usuario: Usuario) -> None:
    if usuario.linea_base_completada:
        raise ErrorApp(MSG_YA_COMPLETADO, 409)
    if not tiene_consentimiento(db, usuario):
        raise ErrorApp(MSG_SIN_CONSENTIMIENTO, 403)


def obtener_cuestionario(db: Session, usuario: Usuario) -> dict:
    """Nunca incluye `correcta`."""
    _exigir_puede_responder(db, usuario)
    cuestionario = cuestionario_activo(db)
    if cuestionario is None:
        raise ErrorApp(MSG_NO_DISPONIBLE, 503)
    try:
        contenido = quitar_clave(cuestionario.contenido)
        return {
            "id": cuestionario.id,
            "version": cuestionario.version,
            "introduccion": contenido.get("introduccion", ""),
            "partes": contenido["partes"],
        }
    except (KeyError, TypeError, AttributeError):
        log.exception("Contenido del cuestionario inválido (id=%s)", cuestionario.id)
        raise ErrorApp(MSG_NO_DISPONIBLE, 503)


# ---------- Validación de completitud ----------
@dataclass
class PreguntaInfo:
    id: str
    parte: int
    tipo: str  # unica | multiple | prueba
    obligatoria: bool
    opciones: dict[str, dict]
    concepto: str | None = None
    motivos: set[str] = field(default_factory=set)
    correcta: str | None = None  # solo Parte 2; nunca se envía al cliente
    nivel: int | None = None
    dificultad: str | None = None


def indexar_preguntas(contenido: dict) -> list[PreguntaInfo]:
    """Aplana el cuestionario en orden: Parte 1, 2 y 3."""
    salida: list[PreguntaInfo] = []
    for numero, parte in enumerate(contenido["partes"], start=1):
        motivos = {m["codigo"] for m in parte.get("omitir_motivos", [])}
        for p in parte["preguntas"]:
            salida.append(
                PreguntaInfo(
                    id=p["id"],
                    parte=numero,
                    tipo=p.get("tipo") or "prueba",
                    obligatoria=bool(p.get("obligatoria", True)),
                    opciones={o["id"]: o for o in p["opciones"]},
                    concepto=p.get("concepto"),
                    motivos=motivos,
                    correcta=p.get("correcta"),
                    nivel=p.get("nivel"),
                    dificultad=p.get("dificultad"),
                )
            )
    return salida


def _revisar_seleccion(info: PreguntaInfo, r: RespuestaIn) -> str | None:
    if r.omitir is not None or r.confianza is not None:
        return "Esta pregunta no admite omitir ni indicar confianza."
    sel = r.opciones
    if info.tipo == "unica":
        if len(sel) != 1:
            return "Elige una sola opción."
    else:
        if not sel:
            return "Selecciona al menos una opción."
        if len(set(sel)) != len(sel):
            return "No repitas opciones."
    if any(o not in info.opciones for o in sel):
        return "Elegiste una opción que no existe en esta pregunta."
    if info.tipo == "multiple" and len(sel) > 1:
        for o in sel:
            if info.opciones[o].get("excluyente"):
                return f"«{info.opciones[o]['texto']}» no se puede combinar con otras opciones."
    return None


def _revisar_prueba(info: PreguntaInfo, r: RespuestaIn) -> str | None:
    if r.omitir is not None:
        if r.opciones or r.confianza is not None:
            return "Si omites la pregunta, no envíes respuesta ni confianza."
        if r.omitir not in info.motivos:
            return "El motivo de omisión no es válido."
        return None
    if not r.opciones:
        return "Elige una respuesta, marca «No sé» u omite la pregunta indicando el motivo."
    if len(r.opciones) != 1:
        return "Elige una sola respuesta."
    opcion = info.opciones.get(r.opciones[0])
    if opcion is None:
        return "Elegiste una opción que no existe en esta pregunta."
    if opcion.get("es_no_se"):
        return None
    if r.confianza is None:
        return "Indica qué tan seguro/a estás (de 1 a 5)."
    if not 1 <= r.confianza <= 5:
        return "La confianza debe ser un número de 1 a 5."
    return None


def validar_respuestas(indice: list[PreguntaInfo], respuestas: list[RespuestaIn]) -> list[dict]:
    """Devuelve la lista de problemas [{campo, mensaje}] en el orden del cuestionario."""
    por_id: dict[str, RespuestaIn] = {}
    problemas: dict[str, str] = {}
    for r in respuestas:
        if r.pregunta_id in por_id:
            problemas[r.pregunta_id] = "Esta pregunta viene repetida en el envío."
        por_id.setdefault(r.pregunta_id, r)
    conocidas = {p.id for p in indice}
    desconocidas = [pid for pid in por_id if pid not in conocidas]

    for info in indice:
        if info.id in problemas:
            continue
        r = por_id.get(info.id)
        if r is None:
            msg = "Falta responder esta pregunta." if info.obligatoria else None
        elif info.tipo == "prueba":
            msg = _revisar_prueba(info, r)
        else:
            msg = _revisar_seleccion(info, r)
        if msg:
            problemas[info.id] = msg

    ordenados = [{"campo": p.id, "mensaje": problemas[p.id]} for p in indice if p.id in problemas]
    ordenados += [{"campo": pid, "mensaje": "Pregunta desconocida."} for pid in desconocidas]
    return ordenados


def _verificaciones_iniciales(db: Session, usuario: Usuario, calculo, reglas: dict) -> list[dict]:
    """R7 al terminar el diagnóstico. El diagnóstico ya está guardado: un fallo aquí no lo deshace."""
    try:
        asignadas = verificaciones.asignar_tras_linea_base(db, usuario.id, calculo.m_por_concepto, reglas)
        return [
            {**asdict(v), "mensaje": mensajes_motor.texto_fijo("verificacion", concepto=v.concepto) or ""} for v in asignadas
        ]
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo asignar la verificación inicial (usuario %s)", usuario.id)
        return []


# ---------- Guardado ----------
def guardar_respuestas(db: Session, usuario: Usuario, datos: RespuestasIn) -> dict:
    _exigir_puede_responder(db, usuario)
    cuestionario = cuestionario_activo(db)
    if cuestionario is None:
        raise ErrorApp(MSG_NO_DISPONIBLE, 503)
    if datos.cuestionario_id is not None and datos.cuestionario_id != cuestionario.id:
        raise ErrorApp("El cuestionario cambió. Recarga la página para ver la versión vigente.", 409)
    try:
        indice = indexar_preguntas(cuestionario.contenido)
    except (KeyError, TypeError, AttributeError):
        log.exception("Contenido del cuestionario inválido (id=%s)", cuestionario.id)
        raise ErrorApp(MSG_NO_DISPONIBLE, 503)

    problemas = validar_respuestas(indice, datos.respuestas)
    if problemas:
        ids = ", ".join(p["campo"] for p in problemas)
        raise ErrorApp(
            f"Revisa las preguntas marcadas antes de enviar: {ids}.",
            422,
            extra={"detalles": problemas, "preguntas_con_problema": [p["campo"] for p in problemas]},
        )

    por_id = {r.pregunta_id: r for r in datos.respuestas}
    try:
        reglas = cargar_reglas()
        conceptos = dict(db.execute(select(Concepto.codigo, Concepto.id)).all())
        for info in indice:
            r = por_id.get(info.id)
            if r is None:
                continue
            if r.omitir is not None:
                db.add(
                    Omision(
                        usuario_id=usuario.id,
                        concepto_id=conceptos[info.concepto],
                        desafio_id=None,
                        motivo=r.omitir,
                        origen="linea_base",
                    )
                )
                continue
            no_se = info.tipo == "prueba" and bool(info.opciones[r.opciones[0]].get("es_no_se"))
            db.add(
                LineaBaseRespuesta(
                    usuario_id=usuario.id,
                    cuestionario_id=cuestionario.id,
                    pregunta_id=info.id,
                    parte=info.parte,
                    opciones=list(r.opciones),
                    confianza=None if no_se else r.confianza,
                    es_no_se=no_se,
                )
            )

        calculo = calcular_linea_base(indice, por_id, list(conceptos), reglas)
        db.add(
            LineaBaseResultado(
                usuario_id=usuario.id,
                cuestionario_id=cuestionario.id,
                m_por_item=calculo.m_por_item,
                m_por_concepto=calculo.m_por_concepto,
                m_por_nivel=calculo.m_por_nivel,
                m_global=calculo.m_global,
                dificultad_inicial=calculo.dificultad_inicial,
                ns_inicial_por_concepto=calculo.ns_inicial,
                preferencias=calculo.preferencias,
                banderas_iniciales=calculo.banderas,
                contexto=calculo.contexto,
                reglas_version=reglas.get("version"),
            )
        )
        # NS inicial (R0): un registro por concepto; el máximo histórico arranca igual.
        existentes = {
            n.concepto_id: n for n in db.scalars(select(NivelSoporte).where(NivelSoporte.usuario_id == usuario.id))
        }
        for codigo, concepto_id in conceptos.items():
            ns = calculo.ns_inicial[codigo]
            fila = existentes.get(concepto_id)
            if fila is None:
                db.add(
                    NivelSoporte(usuario_id=usuario.id, concepto_id=concepto_id, ns=ns, ns_maximo_historico=ns)
                )
            else:
                fila.ns, fila.ns_maximo_historico, fila.desafios_desde_cambio = ns, ns, 0
        usuario.linea_base_completada = True
        db.add(usuario)
        db.commit()
    except IntegrityError:
        db.rollback()
        log.exception("Conflicto al guardar la línea base (¿envío doble?)")
        raise ErrorApp(MSG_YA_COMPLETADO, 409)
    except (SQLAlchemyError, KeyError, TypeError, ValueError, OSError):
        db.rollback()
        log.exception("Error al guardar la línea base")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)

    return {
        "ok": True,
        "mensaje": "¡Listo! Completaste el diagnóstico inicial y tu nivel inicial ya quedó definido.",
        "aviso": None,
        "linea_base_completada": True,
        "verificaciones": _verificaciones_iniciales(db, usuario, calculo, reglas),
    }
