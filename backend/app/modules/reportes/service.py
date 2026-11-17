"""Reportes agregados para docente y administrador (RF-30) y su exportación seudonimizada (RNF-23)."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.core.errores import ErrorApp
from app.core.reglas import cargar_reglas
from app.modules.admin.auditoria import registrar_auditoria
from app.modules.analitica import exportacion, extractores_reportes as ext, reportes as calc, servicio
from app.modules.analitica.reportes import pequeno

log = logging.getLogger("app.reportes")

N_MINIMO_POR_DEFECTO = 3  # si reglas.json no trae la clave, se aplica igual (nunca se muestra con menos)
TIPOS_EXPORTACION = (*exportacion.TIPOS, "todos")
NOTA_PRIVACIDAD = (
    "Los reportes son agregados y usan seudónimos: nunca muestran nombres ni correos. Un grupo con menos de "
    "{n} estudiantes no se muestra (aparece como «suprimido»)."
)


def n_minimo(reglas: dict | None = None) -> int:
    reglas = reglas if reglas is not None else cargar_reglas()
    try:
        return max(2, int(reglas.get("reportes", {}).get("n_minimo", N_MINIMO_POR_DEFECTO)))
    except (TypeError, ValueError):
        return N_MINIMO_POR_DEFECTO


def _iso(f: datetime | None) -> str | None:
    return f.isoformat() if f is not None else None


def reporte(db: Session, desde: datetime | None, hasta: datetime | None) -> dict:
    reglas = cargar_reglas()
    n_min = n_minimo(reglas)
    retiro = tuple(reglas["recaida_y_pausas"]["reglas_que_cuentan_como_retiro"])
    refuerzo = tuple(reglas["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"])
    ventana = reglas["ventana"]

    conceptos = ext.conceptos(db)
    sesiones = ext.sesiones_periodo_df(db, desde, hasta)
    envios = ext.intentos_por_sesion(db, [int(i) for i in sesiones["sesion_id"]])
    cierres = ext.cierres_df(db, hasta)  # toda la historia hasta `hasta`: los indicadores de eficacia la necesitan
    cierres_periodo = cierres[calc.en_periodo(cierres["fin"], desde, None)] if len(cierres) else cierres
    historial = ext.historial_niveles_hasta_df(db, hasta)
    ayudas = ext.ayudas_periodo_df(db, desde, hasta)
    activaciones = ext.activaciones_df(db, ("R9", "R10"), desde, hasta)
    lb_global, lb_concepto = ext.linea_base_periodo(db, desde, hasta)
    por_concepto = servicio.agregados(db, None, desde, hasta)["por_concepto"]  # solo el agregado: nunca por_estudiante

    activos = int(sesiones["usuario_id"].nunique()) if len(sesiones) else 0
    return {
        "periodo": {"desde": _iso(desde), "hasta": _iso(hasta)},
        "generado_en": ahora_utc().isoformat(),
        "n_minimo": n_min,
        "nota_privacidad": NOTA_PRIVACIDAD.format(n=n_min),
        "conceptos": [{"codigo": c["codigo"], "nombre": c["nombre"]} for c in conceptos],
        "resumen": {"estudiantes_activos": None if pequeno(activos, n_min) else activos, "suprimido": pequeno(activos, n_min)},
        "uso": calc.uso_semanal(sesiones, envios, n_min),
        "desempeno": calc.desempeno(cierres_periodo, conceptos, n_min),
        "distribucion_ns": calc.distribucion_ns(por_concepto, conceptos, n_min),
        "ayudas": calc.ayudas_por_tipo(ayudas, n_min),
        "retiros_refuerzos": calc.retiros_y_refuerzos(historial, conceptos, retiro, desde, hasta, n_min),
        "linea_base": calc.linea_base(lb_global, lb_concepto, conceptos, n_min),
        "eficacia": {
            "ns0_sin_recaida": calc.conceptos_ns0_sin_recaida(historial, retiro, desde, hasta, n_min),
            "desafios_hasta_primer_retiro": calc.desafios_hasta_primer_retiro(historial, cierres, conceptos, retiro, desde, hasta, n_min),
            "sa_por_bloque": calc.sa_por_bloque(cierres, int(ventana["tamano"]), desde, hasta, n_min),
            "activacion_r9_r10": calc.activacion_r9_r10(activaciones, int(len(sesiones)), n_min),
            "precision_ns_inicial": calc.precision_ns_inicial(
                historial, cierres, int(ventana["minimo_desafios_desde_cambio"]), retiro, refuerzo, desde, hasta, n_min
            ),
        },
    }


def exportar(db: Session, usuario_id: int, tipo: str, desde: datetime | None, hasta: datetime | None) -> tuple[bytes, str, str]:
    """(contenido, tipo MIME, nombre del archivo). Auditado como `reporte.exportar`: quién exportó qué y cuántas filas."""
    if tipo not in TIPOS_EXPORTACION:
        msg = "El tipo de exportación no es válido. Usa: " + ", ".join(TIPOS_EXPORTACION) + "."
        raise ErrorApp(msg, 422, extra={"detalles": [{"campo": "tipo", "mensaje": msg}]})
    if tipo == "todos":
        contenido, filas = exportacion.todas_en_zip(db, desde, hasta)
        mime, nombre = "application/zip", exportacion.nombre_archivo("exportacion", desde, hasta).removesuffix(".csv") + ".zip"
    else:
        df = exportacion.tabla(db, tipo, desde, hasta)
        contenido, filas = exportacion.a_csv(df).encode("utf-8"), {tipo: len(df)}
        mime, nombre = "text/csv; charset=utf-8", exportacion.nombre_archivo(tipo, desde, hasta)
    registrar_auditoria(
        db, usuario_id, "reporte.exportar", f"reporte:{tipo}",
        {"tipo": tipo, "desde": _iso(desde), "hasta": _iso(hasta), "filas": filas},
    )
    return contenido, mime, nombre
