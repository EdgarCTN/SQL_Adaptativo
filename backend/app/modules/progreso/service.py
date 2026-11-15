"""Resumen de progreso del estudiante (solo lectura sobre datos que ya guardan las demás entregas)."""
import logging
from datetime import datetime
from math import ceil

from sqlalchemy import func, select, union
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApp
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.asistencia.models import SolicitudAyuda
from app.modules.analitica import servicio as analitica
from app.modules.auth.models import Usuario
from app.modules.analitica.models import IndicadorHistorico
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.models import HistorialNivel
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO

log = logging.getLogger("app.progreso")

MAX_CAMBIOS = 10
TIPOS_AYUDA = ("AY1", "AY2", "AY3", "AY4")
MSG_ERROR = "No pudimos cargar tu progreso en este momento. Inténtalo de nuevo."
MSG_ERROR_HISTORIAL = "No pudimos cargar tu historial de intentos en este momento. Inténtalo de nuevo."
MSG_ERROR_EVOLUCION = "No pudimos cargar la evolución de tu progreso en este momento. Inténtalo de nuevo."
MSG_CONCEPTO_NO_EXISTE = "No encontramos ese concepto."
TAM_MAXIMO = 100
RESULTADOS = {
    "correcto": "Correcto",
    "resultado_distinto": "Resultado distinto al esperado",
    "error_sql": "Error de SQL",
    "no_permitida": "Consulta no permitida",
    "varias_sentencias": "Más de una sentencia",
    "tiempo_agotado": "Tiempo agotado",
    "vacia": "Consulta vacía",
}
MSG_SUGERENCIA = "Todavía no tienes actividad. Resuelve tu primer desafío para empezar a ver tu progreso."


def _texto_cambio(regla: str, concepto: str, ns_anterior: int, ns_nuevo: int) -> str:
    """Texto para el estudiante: primer mensaje fijo de la regla; si no hay, uno genérico."""
    try:
        for m in cargar_mensajes_fijos()["mensajes"].values():
            if regla in (m.get("regla") or []) and m.get("texto"):
                return m["texto"].replace("{{concepto}}", concepto)
    except (KeyError, OSError, ValueError, TypeError, AttributeError):
        pass
    return f"Tu nivel de ayuda en {concepto} pasó de {ns_anterior} a {ns_nuevo}."


def resumen(db: Session, usuario: Usuario) -> dict:
    try:
        return _resumen(db, usuario)
    except SQLAlchemyError:
        log.exception("No se pudo calcular el resumen de progreso (usuario %s)", usuario.id)
        raise ErrorApp(MSG_ERROR, 503)


def _resumen(db: Session, usuario: Usuario) -> dict:
    uid = usuario.id
    conceptos = list(db.scalars(select(Concepto).order_by(Concepto.id)))

    # Desafíos resueltos: distintos, y sin contar los que terminaron como NR (vio la solución completa)
    filas = db.execute(
        select(Desafio.concepto_id, SesionDesafio.desafio_id)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .where(
            SesionDesafio.usuario_id == uid,
            SesionDesafio.estado == "resuelto",
            (SesionDesafio.resultado_cierre.is_(None)) | (SesionDesafio.resultado_cierre != "NR"),
        )
        .distinct()
    ).all()
    resueltos_por_concepto: dict[int, int] = {}
    for concepto_id, _ in filas:
        resueltos_por_concepto[concepto_id] = resueltos_por_concepto.get(concepto_id, 0) + 1

    disponibles = db.scalar(select(func.count()).select_from(Desafio).where(Desafio.activo.is_(True))) or 0
    abandonadas = (
        db.scalar(
            select(func.count())
            .select_from(SesionDesafio)
            .where(SesionDesafio.usuario_id == uid, SesionDesafio.estado == "abandonado")
        )
        or 0
    )

    ns_guardado = {
        c_id: int(ns)
        for c_id, ns in db.execute(
            select(NivelSoporte.concepto_id, NivelSoporte.ns).where(NivelSoporte.usuario_id == uid)
        )
    }
    niveles = [
        {
            "codigo": c.codigo,
            "nombre": c.nombre,
            "ns": ns_guardado.get(c.id, NS_POR_DEFECTO),
            "desafios_resueltos": resueltos_por_concepto.get(c.id, 0),
        }
        for c in conceptos
    ]

    ayudas = {t: 0 for t in TIPOS_AYUDA}
    for tipo, n in db.execute(
        select(SolicitudAyuda.tipo_ayuda, func.count()).where(SolicitudAyuda.usuario_id == uid).group_by(SolicitudAyuda.tipo_ayuda)
    ):
        if tipo in ayudas:
            ayudas[tipo] = int(n)
    ayudas["total"] = sum(ayudas[t] for t in TIPOS_AYUDA)

    nombres = {c.id: c.nombre for c in conceptos}
    cambios = [
        {
            "concepto": nombres.get(h.concepto_id, "Concepto"),
            "ns_anterior": h.ns_anterior,
            "ns_nuevo": h.ns_nuevo,
            "texto": _texto_cambio(h.regla, nombres.get(h.concepto_id, "este tema"), h.ns_anterior, h.ns_nuevo),
            "fecha": h.creado_en,
        }
        for h in db.scalars(
            select(HistorialNivel)
            .where(HistorialNivel.usuario_id == uid)
            .order_by(HistorialNivel.creado_en.desc(), HistorialNivel.id.desc())
            .limit(MAX_CAMBIOS)
        )
    ]

    total_resueltos = len(filas)
    hubo_sesion = db.scalar(select(SesionDesafio.id).where(SesionDesafio.usuario_id == uid).limit(1)) is not None
    sin_actividad = not hubo_sesion and ayudas["total"] == 0 and not cambios
    return {
        "sin_actividad": sin_actividad,
        "sugerencia": MSG_SUGERENCIA if sin_actividad else None,
        "desafios_resueltos": total_resueltos,
        "desafios_disponibles": int(disponibles),
        "sesiones_abandonadas": int(abandonadas),
        "diagnostico_completado": bool(usuario.linea_base_completada),
        "niveles": niveles,
        "ayudas": ayudas,
        "cambios_recientes": cambios,
    }


# ---------- Historial de intentos (RF-24) ----------
def _texto_resultado(correcto: bool, resultado_obtenido) -> str:
    if correcto:
        return RESULTADOS["correcto"]
    tipo = resultado_obtenido.get("tipo") if isinstance(resultado_obtenido, dict) else None
    return RESULTADOS.get(tipo, "Incorrecto")


def intentos(
    db: Session, usuario: Usuario, desafio_id: int | None, desde: datetime | None, hasta: datetime | None,
    pagina: int, tam: int,
) -> dict:
    try:
        return _intentos(db, usuario, desafio_id, desde, hasta, pagina, tam)
    except SQLAlchemyError:
        log.exception("No se pudo leer el historial de intentos (usuario %s)", usuario.id)
        raise ErrorApp(MSG_ERROR_HISTORIAL, 503)


def _intentos(
    db: Session, usuario: Usuario, desafio_id: int | None, desde: datetime | None, hasta: datetime | None,
    pagina: int, tam: int,
) -> dict:
    uid = usuario.id
    tam = max(1, min(int(tam), TAM_MAXIMO))
    pagina = max(1, int(pagina))
    condiciones = [SesionDesafio.usuario_id == uid]
    if desafio_id is not None:
        condiciones.append(SesionDesafio.desafio_id == desafio_id)
    if desde is not None:
        condiciones.append(Intento.creado_en >= desde)
    if hasta is not None:
        condiciones.append(Intento.creado_en <= hasta)

    union_sesion = Intento.sesion_id == SesionDesafio.id
    total = (
        db.scalar(select(func.count()).select_from(Intento).join(SesionDesafio, union_sesion).where(*condiciones)) or 0
    )
    filas = db.execute(
        select(
            Intento.id, Intento.sesion_id, Intento.numero, Intento.correcto, Intento.resultado_obtenido, Intento.creado_en,
            SesionDesafio.desafio_id, SesionDesafio.estado, Desafio.titulo, Desafio.dificultad, Concepto.nombre,
        )
        .join(SesionDesafio, union_sesion)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .where(*condiciones)
        .order_by(Intento.creado_en.desc(), Intento.id.desc())
        .offset((pagina - 1) * tam)
        .limit(tam)
    ).all()
    opciones = db.execute(
        select(Desafio.id, Desafio.titulo)
        .join(SesionDesafio, SesionDesafio.desafio_id == Desafio.id)
        .join(Intento, union_sesion)
        .where(SesionDesafio.usuario_id == uid)
        .distinct()
        .order_by(Desafio.titulo)
    ).all()
    return {
        "intentos": [
            {
                "id": f.id, "sesion_id": f.sesion_id, "desafio_id": f.desafio_id, "desafio": f.titulo,
                "concepto": f.nombre, "dificultad": f.dificultad, "numero": f.numero, "correcto": bool(f.correcto),
                "resultado": _texto_resultado(bool(f.correcto), f.resultado_obtenido),
                "estado_sesion": f.estado, "fecha": f.creado_en,
            }
            for f in filas
        ],
        "total": int(total),
        "pagina": pagina,
        "tam": tam,
        "paginas": max(1, ceil(total / tam)),
        "desafios": [{"id": o.id, "titulo": o.titulo} for o in opciones],
    }


# ---------- Evolución de indicadores y del NS (RF-23) ----------
def evolucion(db: Session, usuario: Usuario, concepto: str | None, desde: datetime | None, hasta: datetime | None) -> dict:
    try:
        return _evolucion(db, usuario, concepto, desde, hasta)
    except SQLAlchemyError:
        log.exception("No se pudo leer la evolución (usuario %s)", usuario.id)
        raise ErrorApp(MSG_ERROR_EVOLUCION, 503)


def _evolucion(db: Session, usuario: Usuario, concepto: str | None, desde: datetime | None, hasta: datetime | None) -> dict:
    uid = usuario.id
    conceptos = {c.id: c for c in db.scalars(select(Concepto).order_by(Concepto.id))}
    concepto_id = None
    if concepto:
        elegido = next((c for c in conceptos.values() if c.codigo == concepto), None)
        if elegido is None:
            raise ErrorApp(MSG_CONCEPTO_NO_EXISTE, 404)
        concepto_id = elegido.id

    puntos = analitica.serie_historica(db, uid, concepto_id, desde, hasta)
    cambios = analitica.cambios_de_nivel(db, uid, concepto_id, desde, hasta)

    con_datos = union(
        select(IndicadorHistorico.concepto_id).where(IndicadorHistorico.usuario_id == uid),
        select(HistorialNivel.concepto_id).where(HistorialNivel.usuario_id == uid),
    )
    ids_con_datos = {int(i) for i in db.scalars(con_datos)}
    return {
        "concepto": concepto or None,
        "indicadores": [
            {
                "sesion_id": p["sesion_id"], "concepto": p["concepto_codigo"],
                "concepto_nombre": conceptos[p["concepto_id"]].nombre, "fecha": p["creado_en"],
                "ta": p["ta"], "ni": p["ni"], "tr": p["tr"], "ua": p["ua"],
                "n_ventana": p["n_ventana"], "ns": p["ns"],
            }
            for p in puntos
        ],
        "cambios_ns": [
            {
                "concepto": conceptos[c["concepto_id"]].codigo, "concepto_nombre": conceptos[c["concepto_id"]].nombre,
                "fecha": c["creado_en"], "ns_anterior": c["ns_anterior"], "ns_nuevo": c["ns_nuevo"],
                "texto": _texto_cambio(c["regla"], conceptos[c["concepto_id"]].nombre, c["ns_anterior"], c["ns_nuevo"]),
            }
            for c in cambios
        ],
        "conceptos_con_datos": [
            {"codigo": c.codigo, "nombre": c.nombre} for c in conceptos.values() if c.id in ids_con_datos
        ],
    }
