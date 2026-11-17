from typing import Any

from pydantic import BaseModel


class PeriodoOut(BaseModel):
    desde: str | None = None
    hasta: str | None = None


class ConceptoOut(BaseModel):
    codigo: str
    nombre: str


class ResumenReporteOut(BaseModel):
    estudiantes_activos: int | None = None
    suprimido: bool = False


class EficaciaOut(BaseModel):
    ns0_sin_recaida: dict[str, Any]
    desafios_hasta_primer_retiro: dict[str, Any]
    sa_por_bloque: list[dict[str, Any]]
    activacion_r9_r10: list[dict[str, Any]]
    precision_ns_inicial: dict[str, Any]


class ReporteOut(BaseModel):
    """Solo agregados con seudónimos. Cada tabla marca `suprimido` en los grupos con menos de `n_minimo` estudiantes."""

    periodo: PeriodoOut
    generado_en: str
    n_minimo: int
    nota_privacidad: str
    conceptos: list[ConceptoOut]
    resumen: ResumenReporteOut
    uso: list[dict[str, Any]]
    desempeno: list[dict[str, Any]]
    distribucion_ns: list[dict[str, Any]]
    ayudas: list[dict[str, Any]]
    retiros_refuerzos: list[dict[str, Any]]
    linea_base: dict[str, Any]
    eficacia: EficaciaOut
