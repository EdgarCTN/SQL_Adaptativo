"""Indicadores de la ventana (Matriz, sección 1). El cálculo vive en modules/analitica (pandas); aquí se conserva la firma.

PROVISIONAL: TR usa tiempo_activo_seg (latidos; sin latidos, fin - inicio). UA cuenta pedir o aceptar ayuda, no la mostrada sola.
"""
from dataclasses import dataclass

import pandas as pd

from app.modules.analitica.indicadores import calcular_indicadores_df

EXITOS = ("SA", "CP")


@dataclass(frozen=True)
class CierreReciente:
    resultado: str  # SA | CP | CE | NR
    intentos: int
    tiempo_activo_seg: int | None = None
    tiempo_referencia_seg: int | None = None
    uso_ayuda: bool = False  # pidió o aceptó ayuda en el desafío


@dataclass(frozen=True)
class Indicadores:
    n: int
    ta: float | None
    ni: float | None
    tr: float | None  # None si ningún desafío de la ventana tiene tiempo medido
    ua: float | None = None

    def como_dict(self) -> dict:
        return {"n": self.n, "ta": self.ta, "ni": self.ni, "tr": self.tr, "ua": self.ua}


def calcular_indicadores(cierres: list[CierreReciente]) -> Indicadores:
    df = pd.DataFrame(
        {
            "resultado": [c.resultado for c in cierres],
            "intentos": pd.Series([c.intentos for c in cierres], dtype="float64"),
            "tiempo_activo_seg": pd.Series([c.tiempo_activo_seg for c in cierres], dtype="float64"),
            "tiempo_referencia_seg": pd.Series([c.tiempo_referencia_seg for c in cierres], dtype="float64"),
            "uso_ayuda": pd.Series([bool(c.uso_ayuda) for c in cierres], dtype="bool"),
        }
    )
    return Indicadores(**calcular_indicadores_df(df))
