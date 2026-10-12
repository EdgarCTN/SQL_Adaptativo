import copy

import pytest

from app.core.reglas import cargar_reglas
from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.evaluador import REGLAS_DISPONIBLES, evaluar, ordenar_reglas
from app.modules.motor_retiro.indicadores import CierreReciente, calcular_indicadores
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla


def c(res, intentos=1, t=30, ref=120):
    return CierreReciente(res, intentos, t, ref)


def ctx(ns, cierres, desde=None, config=None):
    return ContextoRegla(
        usuario_id=1, concepto_id=1, concepto_nombre="JOIN", ns_actual=ns, sesion_id=1,
        resultado_sesion=cierres[-1].resultado if cierres else None, cierres_recientes=cierres,
        desafios_desde_cambio=len(cierres) if desde is None else desde, config=config or cargar_reglas(),
    )


SA3 = [c("SA"), c("SA"), c("SA")]

# (nombre, ns, cierres, desde_cambio, regla esperada, ns esperado)
CASOS = [
    # ----- R1 retiro estándar -----
    ("R1 baja de 2 a 1", 2, SA3, None, "R1", 1),
    ("R1 baja de 1 a 0", 1, SA3, None, "R1", 0),
    ("R1 no aplica con NS0", 0, SA3, None, "R4", 0),
    ("R1 CP cuenta como éxito", 2, [c("CP")] * 3, None, "R1", 1),
    ("R1 límite TA=0.80 exacto", 2, [c("SA")] * 4 + [c("CE")], None, "R1", 1),
    ("R1 TA 0.75 no alcanza", 2, [c("SA")] * 3 + [c("CE")], None, "R4", 2),
    ("R1 límite TR=1.25 exacto", 2, [c("SA", 1, 150)] * 3, None, "R1", 1),
    ("R1 TR 1.26 no alcanza", 2, [c("SA", 1, 151)] * 3, None, "R4", 2),
    ("R1 límite NI=2 exacto", 2, [c("SA", 2), c("SA", 2), c("SA", 3)], None, "R1", 1),
    ("R1 NI=3 no alcanza", 2, [c("SA", 3), c("SA", 3), c("SA", 1)], None, "R4", 2),
    ("R1 sin tiempo medido no retira", 2, [c("SA", 1, None)] * 3, None, "R4", 2),
    ("R1 con 2 desafíos: datos insuficientes", 2, [c("SA"), c("SA")], None, "R4", 2),
    ("R1 exige ≥3 desafíos desde el cambio aunque la ventana tenga más", 2, SA3, 2, "R4", 2),
    ("R1 ventana de 5 con 8 desde el cambio", 2, [c("SA")] * 5, 8, "R1", 1),
    # ----- R5 refuerzo -----
    ("R5 sube de 1 a 2", 1, [c("NR")] * 3, None, "R5", 2),
    ("R5 sube de 0 a 1", 0, [c("NR"), c("CE"), c("NR")], None, "R5", 1),
    ("R5 sube de 2 a 3", 2, [c("CE")] * 3, None, "R5", 3),
    ("R5 con NS3 corresponde pero se queda en 3", 3, [c("NR")] * 3, None, "R5", 3),
    ("R5 TA=0.50 exacto no refuerza", 1, [c("SA"), c("SA"), c("CE"), c("CE")], None, "R4", 1),
    ("R5 TA=0.40 de 5", 1, [c("SA"), c("SA")] + [c("NR")] * 3, None, "R5", 2),
    ("R5 NI≥4 con TA<0.80", 1, [c("SA", 4), c("CP", 4), c("CE", 4)], None, "R5", 2),
    ("R5 NI≥4 con TA=0.80 no refuerza", 1, [c("SA", 4)] * 4 + [c("CE", 4)], None, "R4", 1),
    ("R5 NI=3 con TA<0.80 no refuerza", 1, [c("SA", 3), c("CP", 3), c("CE", 3)], None, "R4", 1),
    ("R5 con 2 desafíos: datos insuficientes", 1, [c("NR"), c("NR")], None, "R4", 1),
    # ----- R4 mantener -----
    ("R4 sin cierres", 1, [], 0, "R4", 1),
    ("R4 TA intermedia", 2, [c("SA"), c("CE"), c("SA"), c("CE"), c("SA")], None, "R4", 2),
    ("R4 TA alta con muchos intentos", 2, [c("SA", 4)] * 3, None, "R4", 2),
    ("R4 TA alta con tiempo alto", 2, [c("SA", 1, 600)] * 3, None, "R4", 2),
]


@pytest.mark.parametrize("nombre,ns,cierres,desde,regla,ns_esperado", CASOS, ids=[x[0] for x in CASOS])
def test_tabla_de_casos(nombre, ns, cierres, desde, regla, ns_esperado):
    ev = evaluar(ctx(ns, cierres, desde))
    assert (ev.regla, ev.ns_nuevo) == (regla, ns_esperado), ev.motivo


def test_motivos_legibles():
    assert "datos insuficientes" in evaluar(ctx(1, [c("SA")])).motivo
    assert evaluar(ctx(2, SA3)).motivo.startswith("R1")
    assert "máximo" in evaluar(ctx(3, [c("NR")] * 3)).motivo
    assert evaluar(ctx(2, SA3)).clave_mensaje == "retiro_automatico"
    assert evaluar(ctx(1, [c("NR")] * 3)).clave_mensaje == "refuerzo"
    assert evaluar(ctx(1, [])).clave_mensaje is None


def test_los_umbrales_salen_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["ta_retiro_min"] = 1.0
    assert evaluar(ctx(2, [c("SA")] * 4 + [c("CE")], config=cfg)).regla == "R4"
    cfg = copy.deepcopy(cargar_reglas())
    cfg["ventana"]["minimo_desafios_desde_cambio"] = 2
    assert evaluar(ctx(2, [c("SA"), c("SA")], config=cfg)).regla == "R1"
    cfg["retiro_refuerzo"]["tr_retiro_estandar_max"] = 0.1
    assert evaluar(ctx(2, [c("SA", 1, 60)] * 2, config=cfg)).regla == "R4"


# ---------- Evaluador ----------
class Falsa(Regla):
    def __init__(self, codigo, aplica=True, ns=None):
        self.codigo, self._aplica, self._ns = codigo, aplica, ns

    def aplica(self, contexto):
        return self._aplica

    def ejecutar(self, contexto):
        return ResultadoRegla(self._ns if self._ns is not None else contexto.ns_actual, f"fake {self.codigo}")


def test_orden_r5_r1_r4_segun_reglas_json_y_la_primera_detiene_a_las_demas():
    assert [r.codigo for r in ordenar_reglas(cargar_reglas()["orden_evaluacion_cierre"])] == ["R5", "R1", "R4"]
    disp = {"R5": Falsa("R5", ns=2), "R1": Falsa("R1", ns=0), "R4": Falsa("R4")}
    assert evaluar(ctx(1, SA3), disp).regla == "R5"  # R5 antes que R1 aunque ambas correspondan
    cfg = copy.deepcopy(cargar_reglas())
    cfg["orden_evaluacion_cierre"] = ["R1", "R5", "R4"]
    assert evaluar(ctx(1, SA3, config=cfg), disp).regla == "R1"
    disp["R5"], disp["R1"] = Falsa("R5", aplica=False), Falsa("R1", aplica=False)
    assert evaluar(ctx(1, SA3), disp).regla == "R4"


def test_r4_siempre_cierra_la_secuencia_y_el_ns_se_acota():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["orden_evaluacion_cierre"] = ["R5", "R1"]
    assert [r.codigo for r in ordenar_reglas(cfg["orden_evaluacion_cierre"])][-1] == "R4"
    assert evaluar(ctx(1, SA3), {"R4": Falsa("R4", ns=9)}).ns_nuevo == 3
    assert evaluar(ctx(1, SA3), {"R4": Falsa("R4", ns=-4)}).ns_nuevo == 0
    assert set(REGLAS_DISPONIBLES) == {"R5", "R1", "R4"}


# ---------- Indicadores ----------
def test_indicadores():
    ind = calcular_indicadores([c("SA", 1, 60), c("CP", 2, 120), c("CE", 5, 300), c("NR", 3, 120), c("SA", 1, 120)])
    assert ind.n == 5 and ind.ta == 0.6 and ind.ni == 2.0 and ind.tr == 1.0
    assert calcular_indicadores([]).ta is None
    assert calcular_indicadores([c("SA", 1, None)]).tr is None
    assert calcular_indicadores([c("NR", 0, 30)]).ni == 0.0  # abandonado sin envíos
    assert calcular_indicadores([c("SA", 1, 60), c("SA", 2, 120)]).ni == 1.5  # mediana de dos
