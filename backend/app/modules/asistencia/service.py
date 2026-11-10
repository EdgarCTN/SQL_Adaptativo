import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as TiempoAgotado
from dataclasses import dataclass, replace
from threading import BoundedSemaphore

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.errores import ErrorApp
from app.modules.asistencia import validador
from app.modules.asistencia.config_llm import cargar_llm, cargar_mensajes_fijos
from app.modules.asistencia.decision import decidir_ayuda
from app.modules.asistencia.llm.base import LLMProvider, SolicitudLLM
from app.modules.asistencia.llm.mock import TEXTO_GENERICO
from app.modules.asistencia.models import SolicitudAyuda, ValoracionAyuda
from app.modules.asistencia.preferencias import tono_guardado
from app.modules.asistencia.privacidad import anonimizar
from app.modules.asistencia.prompt_builder import DatosPrompt, construir_prompt, descripciones_errores
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Intento, SesionDesafio
from app.modules.desafios.service import _desafio_activo, _sesion_en_curso
from app.modules.motor_retiro import banderas as banderas_motor
from app.modules.motor_retiro.dependencia import EstadoDependencia, estado_dependencia
from app.modules.motor_retiro.niveles import NivelSoporteService

log = logging.getLogger("app.ayuda")
_EJECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ayuda-llm")
_CUPOS = BoundedSemaphore(4)

MSG_SIN_SESION = "Para pedir ayuda, primero inicia el desafío."
MSG_ERROR_GUARDADO = "No pudimos registrar tu ayuda. Inténtalo de nuevo en unos segundos."
MSG_AYUDA_NO_ENCONTRADA = "No encontramos esa ayuda."
# Provisionales (no están en mensajes_fijos.json)
SUGERENCIA_REINTENTAR = "Antes de pedir más ayuda, prueba a escribir una nueva versión de tu consulta y envíala."
CORRECCION_REINTENTO = (
    "\n\nCORRECCIÓN: tu respuesta anterior no fue válida ({motivo}). "
    "Responde ÚNICAMENTE con el objeto JSON pedido, con el tipo de ayuda indicado en <tipo_ayuda>."
)


def _resumir_resultado(r: dict | None) -> str:
    if not r:
        return ""
    partes = [str(r.get("mensaje") or "")]
    if r.get("columnas"):
        partes.append("columnas: " + ", ".join(map(str, r["columnas"])))
        partes.append(f"filas devueltas: {r.get('total_filas', len(r.get('filas', [])))}")
        partes += ["  " + " | ".join("NULL" if v is None else str(v) for v in f) for f in (r.get("filas") or [])[:5]]
    if r.get("detalle_tecnico"):
        partes.append("detalle técnico: " + str(r["detalle_tecnico"]))
    return "\n".join(p for p in partes if p)


def _etiquetas_respaldo() -> tuple[str, ...]:
    cfg = cargar_llm()
    return (cfg["etiqueta_ia"], cfg["etiqueta_mock"])


def _ayuda_respaldo(desafio, tipo: str) -> dict | None:
    """Ayuda de respaldo guardada para el tipo ({mensaje, codigo_sql}); tolera formas mal guardadas."""
    ay = desafio.ayudas_respaldo.get(tipo) if isinstance(desafio.ayudas_respaldo, dict) else None
    if isinstance(ay, str):
        return {"mensaje": ay, "codigo_sql": None}
    return ay if isinstance(ay, dict) else None


def _respaldo(desafio, tipo: str) -> dict:
    ay = _ayuda_respaldo(desafio, tipo) or {}
    return {"mensaje": ay.get("mensaje") or TEXTO_GENERICO, "codigo_sql": ay.get("codigo_sql")}


def _pedir_al_llm(proveedor: LLMProvider, solicitud: SolicitudLLM, contexto: dict | None = None) -> tuple[object | None, validador.ResultadoValidacion | None, list[str]]:
    """Generación y validación comparten un plazo total; V9 nunca provoca otro intento.

    Los trabajadores no acceden a la sesión SQLAlchemy. Un resultado tardío se descarta y no se guarda.
    La concurrencia está acotada para que una dependencia lenta no cree una cola ilimitada.
    """
    incidentes: list[str] = []
    actual = solicitud
    inicio = time.monotonic()
    limite = float(cargar_llm()["tiempo_limite_seg"])

    def generar_y_validar(pedido):
        try:
            respuesta = proveedor.generar(pedido)
            validacion = validador.validar(
                respuesta.texto, solicitud.tipo_ayuda, **(contexto or {}),
                segundos=time.monotonic() - inicio, limite_seg=limite,
            )
            return respuesta, validacion
        finally:
            _CUPOS.release()

    for intento in range(1 + int(cargar_llm()["reintentos"])):
        restante = limite - (time.monotonic() - inicio)
        if restante <= 0 or not _CUPOS.acquire(blocking=False):
            incidentes.append("V9: tiempo límite o capacidad de ayuda agotados")
            break
        futuro = _EJECUTOR.submit(generar_y_validar, replace(actual, tiempo_limite_seg=restante))
        try:
            respuesta, res = futuro.result(timeout=restante)
        except TiempoAgotado:
            if futuro.cancel():
                _CUPOS.release()
            incidentes.append("V9: tiempo límite de ayuda agotado")
            break
        except Exception as e:  # noqa: BLE001  (el estudiante nunca ve un error técnico)
            log.warning("Falló el LLM o el validador (%s)", type(e).__name__)
            incidentes.append(f"error: {type(e).__name__}")
            res, respuesta = None, None
        else:
            if time.monotonic() - inicio > limite:
                incidentes.append("V9: tiempo límite de ayuda agotado")
                break
            if res.ok:
                return respuesta, res, incidentes
            incidentes.append(res.motivo or "validación fallida")
            log.warning("Respuesta del LLM rechazada en %s: %s", solicitud.tipo_ayuda, res.motivo)
            if (res.motivo or "").startswith("V9"):
                break
            actual = SolicitudLLM(
                solicitud.tipo_ayuda,
                solicitud.prompt_sistema,
                solicitud.mensaje_usuario + CORRECCION_REINTENTO.format(motivo=res.motivo),
                solicitud.ayuda_respaldo,
            )
    return None, None, incidentes


def _banderas_prompt(db: Session, usuario_id: int, dependencia: bool) -> list[str]:
    """Solo los códigos de la plantilla (R9 «dependencia», R11 «sobreconfianza»): nunca números ni indicadores."""
    codigos = []
    if dependencia:
        codigos.append("dependencia")
    if banderas_motor.sobreconfianza_inicial(db, usuario_id):
        codigos.append("sobreconfianza")
    return codigos


@dataclass(frozen=True)
class EstadoAyuda:
    """Lo que la decisión de ayuda necesita saber de la sesión en curso."""

    previas: list  # SolicitudAyuda de la sesión, en orden
    tipos_previos: list[str]
    intentos: list  # Intento de la sesión, en orden
    fallos: int
    desde_ultima: int  # fallos posteriores a la última ayuda entregada


def estado_ayuda(db: Session, sesion: SesionDesafio) -> EstadoAyuda:
    previas = list(
        db.scalars(select(SolicitudAyuda).where(SolicitudAyuda.sesion_id == sesion.id).order_by(SolicitudAyuda.id))
    )
    intentos = list(db.scalars(select(Intento).where(Intento.sesion_id == sesion.id).order_by(Intento.numero)))
    ultima = previas[-1] if previas else None
    # Los IDs/números de intento son un corte estable; los datetimes SQLite pueden
    # empatar si un intento y una ayuda ocurren en el mismo tick del reloj.
    corte_intentos = ultima.intentos_previos if ultima and ultima.intentos_previos is not None else None
    momento_ultima = ultima.momento if ultima else None
    return EstadoAyuda(
        previas=previas,
        tipos_previos=[s.tipo_ayuda for s in previas],
        intentos=intentos,
        fallos=sum(1 for i in intentos if not i.correcto),
        desde_ultima=sum(
            1 for i in intentos if not i.correcto and (
                i.numero > corte_intentos if corte_intentos is not None
                else momento_ultima is None or i.creado_en > momento_ultima
            )
        ),
    )


def dependencia_de(db: Session, usuario_id: int, concepto_id: int) -> EstadoDependencia | None:
    """R9 para este concepto; si falla el cálculo se sigue sin ella (la ayuda nunca se rompe por una bandera)."""
    try:
        return estado_dependencia(db, usuario_id, concepto_id)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("No se pudo evaluar R9 (usuario %s, concepto %s)", usuario_id, concepto_id)
        return None


def solicitar_ayuda(
    db: Session, usuario: Usuario, desafio_id: int, mensaje_estudiante: str | None, proveedor: LLMProvider,
    mostrada_sola: bool = False,
) -> dict:
    d = _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    if sesion is None:
        raise ErrorApp(MSG_SIN_SESION, 409)

    est = estado_ayuda(db, sesion)
    previas, tipos_previos, intentos, fallos = est.previas, est.tipos_previos, est.intentos, est.fallos

    ns = NivelSoporteService(db).obtener(usuario.id, d.concepto_id)
    dep = dependencia_de(db, usuario.id, d.concepto_id)  # R9: +1 al mínimo de fallos de AY3 y AY4
    en_dependencia = bool(dep and dep.activa)
    decision = decidir_ayuda(ns, fallos, tipos_previos, est.desde_ultima, dependencia=en_dependencia)
    mensajes_fijos = cargar_mensajes_fijos()["mensajes"]
    if decision.ya_vio_ay4:  # solo se le recuerda; no se llama al LLM
        return {"aviso": mensajes_fijos["solucion_ya_mostrada"]["texto"], "desafio_marcado_nr": True}

    tipo = decision.tipo
    personales = tuple({usuario.nombre, usuario.correo, *(p for p in usuario.nombre.split() if len(p) > 2)})
    previas_texto = [
        anonimizar(f"{s.tipo_ayuda}: {s.texto_entregado[:400]}; código: {(s.codigo_sql or '')[:400]}", personales)
        for s in previas[-5:]
    ]
    if decision.reformulada and previas:
        previas_texto[-1] += " (ya entregada; redáctala distinto)"
    ultimo = intentos[-1] if intentos else None
    concepto = db.get(Concepto, d.concepto_id)
    datos = DatosPrompt(
        tipo_ayuda=tipo,
        concepto=concepto.nombre,
        dificultad=d.dificultad,
        enunciado=d.enunciado,
        esquema_sql=d.esquema_sql,
        errores_tipicos=descripciones_errores(d.errores_tipicos),
        intento=len(intentos),
        fallos=fallos,
        tiempo_relativo=max(0.0, (ahora_utc() - sesion.inicio).total_seconds()) / d.tiempo_referencia_seg,
        ayudas_previas=previas_texto,
        historial_errores=[anonimizar(
            f"Intento {i.numero}: {i.codigo[:400]} — {_resumir_resultado(i.resultado_obtenido)[:600]}", personales
        ) for i in intentos[-5:] if not i.correcto],
        codigo_estudiante=anonimizar(ultimo.codigo if ultimo else "", personales),
        resultado_obtenido=anonimizar(_resumir_resultado(ultimo.resultado_obtenido) if ultimo else "", personales),
        mensaje_estudiante=anonimizar(mensaje_estudiante or "", personales),
        solucion_referencia=d.solucion_referencia,
        tono=tono_guardado(db, usuario.id),
        banderas=_banderas_prompt(db, usuario.id, en_dependencia),
    )
    prompt = construir_prompt(datos)
    solicitud = SolicitudLLM(tipo, prompt.prompt_sistema, prompt.mensaje_usuario, _ayuda_respaldo(d, tipo))

    respuesta, valida, incidentes = _pedir_al_llm(proveedor, solicitud, {
        "solucion": d.solucion_referencia, "esquema": d.esquema_sql,
        "setup": d.sandbox_setup_sql, "personales": personales,
    })
    if valida is not None:
        cuerpo = {"mensaje": valida.datos["mensaje"].strip(), "codigo_sql": valida.datos["codigo_sql"]}
        etiquetas = tuple(respuesta.etiquetas) or (cargar_llm()["etiqueta_ia"],)
        fue_respaldo, nombre_proveedor = bool(respuesta.es_respaldo), respuesta.proveedor
    else:  # EX1/EX2: ayuda de respaldo, nunca un error técnico
        cuerpo = _respaldo(d, tipo)
        etiquetas, fue_respaldo, nombre_proveedor = _etiquetas_respaldo(), True, "respaldo"

    registro = SolicitudAyuda(
        sesion_id=sesion.id,
        usuario_id=usuario.id,
        desafio_id=d.id,
        tipo_ayuda=tipo,
        momento=ahora_utc(),
        fue_respaldo=fue_respaldo,
        proveedor=nombre_proveedor,
        texto_entregado=cuerpo["mensaje"],
        codigo_sql=cuerpo["codigo_sql"],
        incidente_validacion="; ".join(incidentes) or None,
        mostrada_sola=mostrada_sola,
        tipo_solicitado=decision.solicitado,
        intentos_previos=len(intentos),
    )
    db.add(registro)
    if mostrada_sola:
        sesion.ayuda_mostrada_sola = True  # no cuenta para UA ni para R9 (marca de la solicitud y de la sesión)
    if tipo == "AY4":
        sesion.resultado_cierre = "NR"  # NR de inmediato; la sesión sigue en curso
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo registrar la solicitud de ayuda")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    if en_dependencia and not mostrada_sola and not banderas_motor.ya_registrada(db, usuario.id, sesion.id, "R9"):
        banderas_motor.registrar_activacion(  # R9: una vez por desafío en que modifica la ayuda
            db, usuario.id, d.concepto_id, sesion.id, "R9",
            f"R9 dependencia ({dep.origen}): mínimos de AY3 y AY4 con +1; bandera «dependencia» hacia el prompt",
            dep.como_dict(), ns,
        )
    return {
        "solicitud_id": registro.id,
        "tipo_ayuda": tipo,
        "mensaje": cuerpo["mensaje"],
        "codigo_sql": cuerpo["codigo_sql"],
        "etiquetas": list(etiquetas),
        "fue_respaldo": fue_respaldo,
        "reformulada": decision.reformulada,
        "sugerencia": SUGERENCIA_REINTENTAR if decision.degradada else None,
        "aviso": mensajes_fijos["solucion_ya_mostrada"]["texto"] if tipo == "AY4" else None,
        "desafio_marcado_nr": tipo == "AY4",
        "mostrada_sola": mostrada_sola,
    }


def listar_ayudas(db: Session, usuario: Usuario, desafio_id: int, sesion_id: int | None = None) -> dict:
    """Solo el historial propio: sesión indicada, actual o última, sin revelar registros ajenos."""
    _desafio_activo(db, desafio_id)
    consulta = select(SesionDesafio).where(
        SesionDesafio.usuario_id == usuario.id, SesionDesafio.desafio_id == desafio_id,
    )
    if sesion_id is not None:
        consulta = consulta.where(SesionDesafio.id == sesion_id)
    sesion = db.scalar(consulta.order_by((SesionDesafio.estado == "en_curso").desc(), SesionDesafio.id.desc()).limit(1))
    if sesion is None:
        if sesion_id is not None:
            raise ErrorApp(MSG_AYUDA_NO_ENCONTRADA, 404)
        return {"sesion_id": None, "ayudas": []}
    filas = db.execute(select(SolicitudAyuda, ValoracionAyuda.valor).outerjoin(
        ValoracionAyuda, (ValoracionAyuda.solicitud_id == SolicitudAyuda.id) & (ValoracionAyuda.usuario_id == usuario.id),
    ).where(SolicitudAyuda.sesion_id == sesion.id).order_by(SolicitudAyuda.id)).all()
    cfg = cargar_llm()
    return {"sesion_id": sesion.id, "ayudas": [{
        "solicitud_id": s.id, "tipo_ayuda": s.tipo_ayuda, "mensaje": s.texto_entregado,
        "codigo_sql": s.codigo_sql, "fue_respaldo": s.fue_respaldo, "mostrada_sola": s.mostrada_sola,
        "etiquetas": list(_etiquetas_respaldo()) if s.fue_respaldo else [cfg["etiqueta_ia"]],
        "valoracion": valor, "momento": s.momento,
        "aviso": cargar_mensajes_fijos()["mensajes"]["solucion_ya_mostrada"]["texto"] if s.tipo_ayuda == "AY4" else None,
        "desafio_marcado_nr": s.tipo_ayuda == "AY4",
    } for s, valor in filas]}


def valorar(db: Session, usuario: Usuario, solicitud_id: int, valor: int) -> dict:
    s = db.get(SolicitudAyuda, solicitud_id)
    if s is None or s.usuario_id != usuario.id:
        raise ErrorApp(MSG_AYUDA_NO_ENCONTRADA, 404)
    v = db.scalar(
        select(ValoracionAyuda).where(ValoracionAyuda.solicitud_id == s.id, ValoracionAyuda.usuario_id == usuario.id)
    )
    if v is None:
        db.add(ValoracionAyuda(solicitud_id=s.id, usuario_id=usuario.id, valor=valor))
    else:
        v.valor = valor
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    return {"ok": True, "valor": valor}
