"""Indicadores de la ventana (Tabla 4). Hueco listo para pandas: basta con reemplazar calcular_indicadores.

Hoy se calculan en Python puro con los cierres del concepto:
- TA = éxitos (SA o CP) ÷ desafíos de la ventana.
- NI = mediana de envíos por desafío (en un NR, los envíos realizados).
- TR = mediana de (tiempo activo ÷ tiempo de referencia). PROVISIONAL: «tiempo activo real» no está definido
  en los documentos; se usa sesiones_desafio.tiempo_activo_seg (= fin − inicio, incluye pausas).
- UA (uso de ayuda) no se calcula: R1 y R5 no la usan.
"""
from dataclasses import dataclass
from statistics import median

EXITOS = ("SA", "CP")


@dataclass(frozen=True)
class CierreReciente:
    resultado: str  # SA | CP | CE | NR
    intentos: int
    tiempo_activo_seg: int | None = None
    tiempo_referencia_seg: int | None = None


@dataclass(frozen=True)
class Indicadores:
    n: int
    ta: float | None
    ni: float | None
    tr: float | None  # None si ningún desafío de la ventana tiene tiempo medido

    def como_dict(self) -> dict:
        return {"n": self.n, "ta": self.ta, "ni": self.ni, "tr": self.tr}


def calcular_indicadores(cierres: list[CierreReciente]) -> Indicadores:
    if not cierres:
        return Indicadores(0, None, None, None)
    ta = sum(1 for c in cierres if c.resultado in EXITOS) / len(cierres)
    ni = float(median(c.intentos for c in cierres))
    razones = [
        c.tiempo_activo_seg / c.tiempo_referencia_seg
        for c in cierres
        if c.tiempo_activo_seg is not None and c.tiempo_referencia_seg
    ]
    tr = float(median(razones)) if razones else None
    return Indicadores(len(cierres), round(ta, 6), round(ni, 6), None if tr is None else round(tr, 6))
