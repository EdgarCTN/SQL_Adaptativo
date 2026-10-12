import logging

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
from app.modules.asistencia.prompt_builder import DatosPrompt, construir_prompt, descripciones_errores
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Intento
from app.modules.desafios.service import _desafio_activo, _sesion_en_curso
from app.modules.motor_retiro.niveles import NivelSoporteService

log = logging.getLogger("app.ayuda")

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


def _pedir_al_llm(proveedor: LLMProvider, solicitud: SolicitudLLM) -> tuple[object | None, validador.ResultadoValidacion | None, list[str]]:
    """Llama al LLM y valida. Un reintento agregando el motivo. Devuelve (respuesta, validación ok, incidentes)."""
    incidentes: list[str] = []
    actual = solicitud
    for intento in range(1 + int(cargar_llm()["reintentos"])):
        try:
            respuesta = proveedor.generar(actual)
            res = validador.validar(respuesta.texto, solicitud.tipo_ayuda)
        except Exception as e:  # noqa: BLE001  (el estudiante nunca ve un error técnico)
            log.warning("Falló el LLM o el validador (%s)", type(e).__name__)
            incidentes.append(f"error: {type(e).__name__}")
            res, respuesta = None, None
        else:
            if res.ok:
                return respuesta, res, incidentes
            incidentes.append(res.motivo or "validación fallida")
            actual = SolicitudLLM(
                solicitud.tipo_ayuda,
                solicitud.prompt_sistema,
                solicitud.mensaje_usuario + CORRECCION_REINTENTO.format(motivo=res.motivo),
                solicitud.ayuda_respaldo,
            )
    return None, None, incidentes


def solicitar_ayuda(db: Session, usuario: Usuario, desafio_id: int, mensaje_estudiante: str | None, proveedor: LLMProvider) -> dict:
    d = _desafio_activo(db, desafio_id)
    sesion = _sesion_en_curso(db, usuario.id, d.id)
    if sesion is None:
        raise ErrorApp(MSG_SIN_SESION, 409)

    previas = list(
        db.scalars(select(SolicitudAyuda).where(SolicitudAyuda.sesion_id == sesion.id).order_by(SolicitudAyuda.id))
    )
    tipos_previos = [s.tipo_ayuda for s in previas]
    intentos = list(db.scalars(select(Intento).where(Intento.sesion_id == sesion.id).order_by(Intento.numero)))
    fallos = sum(1 for i in intentos if not i.correcto)
    momento_ultima = previas[-1].momento if previas else None
    desde_ultima = sum(1 for i in intentos if not i.correcto and (momento_ultima is None or i.creado_en > momento_ultima))

    ns = NivelSoporteService(db).obtener(usuario.id, d.concepto_id)
    decision = decidir_ayuda(ns, fallos, tipos_previos, desde_ultima)
    mensajes_fijos = cargar_mensajes_fijos()["mensajes"]
    if decision.ya_vio_ay4:  # solo se le recuerda; no se llama al LLM
        return {"aviso": mensajes_fijos["solucion_ya_mostrada"]["texto"], "desafio_marcado_nr": True}

    tipo = decision.tipo
    previas_texto = list(tipos_previos)
    if decision.reformulada and previas:
        previas_texto[-1] = f"{tipos_previos[-1]} (ya entregada; redáctala distinto: {' '.join(previas[-1].texto_entregado.split())[:400]})"
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
        codigo_estudiante=ultimo.codigo if ultimo else "",
        resultado_obtenido=_resumir_resultado(ultimo.resultado_obtenido) if ultimo else "",
        mensaje_estudiante=mensaje_estudiante or "",
        solucion_referencia=d.solucion_referencia,
        tono=tono_guardado(db, usuario.id),
        banderas=[],  # fuera del MVP
    )
    prompt = construir_prompt(datos)
    solicitud = SolicitudLLM(tipo, prompt.prompt_sistema, prompt.mensaje_usuario, _ayuda_respaldo(d, tipo))

    respuesta, valida, incidentes = _pedir_al_llm(proveedor, solicitud)
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
    )
    db.add(registro)
    if tipo == "AY4":
        sesion.resultado_cierre = "NR"  # NR de inmediato; la sesión sigue en curso
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo registrar la solicitud de ayuda")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
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
    }


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
