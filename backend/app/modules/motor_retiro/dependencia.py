"""R9 Dependencia (Matriz, Tabla 9, bloque 5). Condiciona al resto: no está en la secuencia de evaluación.

- Bandera inicial: la línea base cumple ≥ 2 de 3 señales (calculada al registrarse; ver linea_base.calculo).
- Bandera dinámica, con la capa analítica, sobre la ventana del concepto: UA ≥ 80 % de los desafíos, o ≥ 50 % de los
  pedidos de ayuda son AY3/AY4 con ≤ 1 envío previo. Se reevalúa cuando la ventana tiene al menos 3 desafíos
  (`r9_dependencia.desafios_minimos_para_reevaluar`); con menos, rige la bandera inicial.
  PROVISIONAL: «reevaluar» reemplaza a la inicial (con ≥ 3 desafíos manda la ventana, no se suman).
- Efecto: +1 al mínimo de fallos de AY3 y AY4 (asistencia.decision) y la bandera `dependencia` hacia el prompt.
Las ayudas mostradas solas (preferencia 3.3) no cuentan: ni para la UA ni para los pedidos directos.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import cargar_reglas
from app.modules.analitica.extractores import cierres_del_concepto, pedidos_df
from app.modules.analitica.indicadores import calcular_ua, proporcion_pedidos_directos, ventana
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.banderas import dependencia_inicial

TIPOS_DIRECTOS = ("AY3", "AY4")
ORIGEN_DINAMICA, ORIGEN_INICIAL, ORIGEN_NINGUNO = "dinamica", "inicial", "ninguno"


@dataclass(frozen=True)
class EstadoDependencia:
    activa: bool
    origen: str  # dinamica | inicial | ninguno
    evaluable: bool  # la ventana tiene los desafíos mínimos para reevaluar
    n: int
    ua: float | None
    pedidos_directos: float | None
    inicial: bool

    def como_dict(self) -> dict:
        return {
            "activa": self.activa, "origen": self.origen, "evaluable": self.evaluable, "n": self.n, "ua": self.ua,
            "pedidos_directos": self.pedidos_directos, "inicial": self.inicial,
        }


def cumple_criterio(ua: float | None, pedidos_directos: float | None, cfg: dict) -> bool:
    """Criterio dinámico de R9 (función pura)."""
    por_ua = ua is not None and round(ua, 6) >= cfg["pct_desafios_con_ayuda_min"]
    por_pedidos = pedidos_directos is not None and round(pedidos_directos, 6) >= cfg["pct_pedidos_ay3_ay4_con_pocos_intentos_min"]
    return bool(por_ua or por_pedidos)


def estado_dependencia(db: Session, usuario_id: int, concepto_id: int, reglas: dict | None = None) -> EstadoDependencia:
    reglas = reglas or cargar_reglas()
    cfg = reglas["r9_dependencia"]
    inicial = dependencia_inicial(db, usuario_id)
    fila = db.scalar(select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto_id))
    df = cierres_del_concepto(db, usuario_id, concepto_id, desde=fila.ultimo_cambio_en if fila is not None else None)
    v = ventana(df, int(reglas["ventana"]["tamano"]))
    n = int(len(v))
    if n < int(cfg["desafios_minimos_para_reevaluar"]):
        return EstadoDependencia(inicial, ORIGEN_INICIAL if inicial else ORIGEN_NINGUNO, False, n, None, None, inicial)
    ua = calcular_ua(v)
    pedidos = proporcion_pedidos_directos(
        pedidos_df(db, [int(s) for s in v["sesion_id"]]), TIPOS_DIRECTOS, int(cfg["intentos_previos_max_para_pedido_directo"])
    )
    activa = cumple_criterio(ua, pedidos, cfg)
    return EstadoDependencia(activa, ORIGEN_DINAMICA if activa else ORIGEN_NINGUNO, True, n, ua, pedidos, inicial)
