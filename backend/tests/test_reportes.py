"""Entrega 13B: reportes agregados y exportación seudonimizada (RF-30, RNF-23)."""
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select

from app.core.reglas import cargar_reglas
from app.core.seguridad import hashear_password
from app.modules.admin.models import Auditoria
from app.modules.analitica import reportes as calc
from app.modules.analitica.models import IndicadorHistorico
from app.modules.analitica.seudonimizar import id_pseudonimo
from app.modules.asistencia.models import SolicitudAyuda, ValoracionAyuda
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import LineaBaseCuestionario, LineaBaseResultado
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from app.modules.reportes import service
from conftest import API, cabecera, registrar, token_de

RAIZ = Path(__file__).resolve().parents[2]
LUNES = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

# Nombres y correos reconocibles: ninguna salida debe contener ni un fragmento.
PERSONAS = [
    ("Zoila Quispe Huamán", "zoila.quispe@secreto.edu"),
    ("Wilmer Anccasi Rojas", "wilmer.anccasi@secreto.edu"),
    ("Yeni Chambilla Soto", "yeni.chambilla@secreto.edu"),
    ("Octavio Mamani Paredes", "octavio.mamani@secreto.edu"),
]
FRAGMENTOS_PERSONALES = ["zoila", "quispe", "huam", "wilmer", "anccasi", "yeni", "chambilla", "octavio", "mamani", "secreto", "@"]


def dia(n: int, horas: int = 0) -> datetime:
    return LUNES + timedelta(days=n, hours=horas)


class Mundo:
    """Datos sintéticos controlados: se escriben directo en la base para conocer cada cifra esperada."""

    def __init__(self, db):
        self.db = db
        self.usuarios: list[Usuario] = []
        self.sesiones: dict[tuple[int, str, int], SesionDesafio] = {}
        for nombre, correo in PERSONAS:
            u = Usuario(nombre=nombre, correo=correo, rol=Rol.estudiante.value, hash_password=hashear_password("Clave12345"))
            db.add(u)
            self.usuarios.append(u)
        db.commit()

    def concepto(self, codigo: str) -> Concepto:
        return self.db.scalar(select(Concepto).where(Concepto.codigo == codigo))

    def desafio(self, codigo: str) -> Desafio:
        return self.db.scalars(select(Desafio).where(Desafio.concepto_id == self.concepto(codigo).id).order_by(Desafio.id)).first()

    def cerrar(self, i: int, codigo: str, resultado: str, d: int, envios: int = 1, ns_tras: int = 1) -> SesionDesafio:
        """El estudiante i cierra un desafío del concepto `codigo` el día `d` (fin = inicio + 1 h)."""
        u, des = self.usuarios[i], self.desafio(codigo)
        s = SesionDesafio(
            usuario_id=u.id, desafio_id=des.id, inicio=dia(d), fin=dia(d, 1), tiempo_activo_seg=int(des.tiempo_referencia_seg),
            estado="abandonado" if resultado == "NR" else "resuelto", resultado_cierre=resultado,
        )
        self.db.add(s)
        self.db.flush()
        for n in range(1, envios + 1):
            self.db.add(Intento(sesion_id=s.id, numero=n, codigo="SELECT 1 -- codigo del estudiante", correcto=(n == envios and resultado != "NR"), creado_en=dia(d, 0) + timedelta(minutes=n)))
        self.db.add(IndicadorHistorico(
            usuario_id=u.id, concepto_id=des.concepto_id, sesion_id=s.id, ta=1.0, ni=1.0, tr=1.0, ua=0.0, n_ventana=1, ns=ns_tras, creado_en=dia(d, 1),
        ))
        self.db.commit()
        return s

    def cambio(self, i: int, codigo: str, antes: int, despues: int, regla: str, cuando: datetime) -> None:
        self.db.add(HistorialNivel(usuario_id=self.usuarios[i].id, concepto_id=self.concepto(codigo).id, ns_anterior=antes, ns_nuevo=despues, regla=regla, motivo="x", creado_en=cuando))
        self.db.commit()

    def ayuda(self, i: int, sesion: SesionDesafio, tipo: str, valor: int | None = None, sola: bool = False) -> None:
        a = SolicitudAyuda(
            sesion_id=sesion.id, usuario_id=self.usuarios[i].id, desafio_id=sesion.desafio_id, tipo_ayuda=tipo, proveedor="mock",
            texto_entregado="Texto de la ayuda", mostrada_sola=sola, tipo_solicitado=tipo, intentos_previos=0, momento=sesion.inicio + timedelta(minutes=5),
        )
        self.db.add(a)
        self.db.flush()
        if valor is not None:
            self.db.add(ValoracionAyuda(solicitud_id=a.id, usuario_id=self.usuarios[i].id, valor=valor))
        self.db.commit()

    def evento(self, i: int, regla: str, sesion: SesionDesafio) -> None:
        self.db.add(EventoMotor(usuario_id=self.usuarios[i].id, concepto_id=self.desafio_de(sesion).concepto_id, sesion_id=sesion.id, regla=regla, resultado="mantiene", creado_en=sesion.inicio + timedelta(minutes=10)))
        self.db.commit()

    def desafio_de(self, sesion: SesionDesafio) -> Desafio:
        return self.db.get(Desafio, sesion.desafio_id)

    def linea_base(self, i: int, m_global: float, m_filtrado: float, m_join: float | None = None) -> None:
        por_concepto = {"filtrado": {"m": m_filtrado}}
        if m_join is not None:
            por_concepto["join"] = {"m": m_join}
        self.db.add(LineaBaseResultado(
            usuario_id=self.usuarios[i].id, cuestionario_id=self.db.scalar(select(LineaBaseCuestionario.id)), m_global=m_global,
            m_por_concepto=por_concepto, creado_en=dia(-1),
        ))
        self.db.commit()


@pytest.fixture
def mundo(client, db) -> Mundo:
    """4 estudiantes. `filtrado` (4 estudiantes, 12 cierres) se muestra; `join` (2 estudiantes) queda suprimido."""
    m = Mundo(db)
    f = "filtrado"
    s = {}
    # E1 y E2: tres SA y retiro R2 a NS 0.   E3: SA, CP, SA y retiro R1; luego recae (R3).   E4: sin cambios (NR, SA, CE).
    for i in (0, 1):
        for d in range(3):
            s[(i, d)] = m.cerrar(i, f, "SA", d, ns_tras=1 if d < 2 else 0)
    for d, r in enumerate(("SA", "CP", "SA")):
        s[(2, d)] = m.cerrar(2, f, r, d, ns_tras=1 if d < 2 else 0)
    for d, (r, e) in enumerate((("NR", 2), ("SA", 1), ("CE", 3))):
        s[(3, d)] = m.cerrar(3, f, r, d, envios=e)
    for i, regla in ((0, "R2"), (1, "R2"), (2, "R1")):
        m.cambio(i, f, 1, 0, regla, dia(2, 1) + timedelta(minutes=5))
    m.cambio(2, f, 0, 1, "R3", dia(5))
    # `join`: solo 2 estudiantes (grupo pequeño). E2 en la semana 1 y E1 en la semana 2 (con un refuerzo R5).
    s["j2"] = m.cerrar(1, "join", "SA", 3)
    s["j1"] = m.cerrar(0, "join", "CP", 8)
    m.cambio(0, "join", 1, 2, "R5", dia(8, 1) + timedelta(minutes=5))
    # Ayudas: AY1 de tres estudiantes (grupo visible; una mostrada sola); AY2 de un estudiante (suprimida).
    m.ayuda(0, s[(0, 0)], "AY1", valor=1)
    m.ayuda(1, s[(1, 0)], "AY1", valor=1)
    m.ayuda(2, s[(2, 0)], "AY1", valor=-1, sola=True)
    m.ayuda(0, s[(0, 1)], "AY2", valor=1)
    # R9 en tres estudiantes (visible), R10 en uno (suprimida).
    for i in (0, 1, 2):
        m.evento(i, "R9", s[(i, 0)])
    m.evento(0, "R10", s[(0, 1)])
    for i, (g, f_, j) in enumerate(((0.8, 0.9, 0.7), (0.6, 0.5, 0.6), (0.4, 0.3, None), (0.2, 0.1, None))):
        m.linea_base(i, g, f_, j)
    m.s = s
    return m


def tokens(client, db):
    for rol, correo in ((Rol.docente, "profe@uni.edu"), (Rol.administrador, "jefe@uni.edu")):
        db.add(Usuario(nombre="Staff", correo=correo, rol=rol.value, hash_password=hashear_password("Clave12345")))
    db.commit()
    registrar(client)
    return {
        "estudiante": cabecera(token_de(client)),
        "docente": cabecera(token_de(client, "profe@uni.edu")),
        "administrador": cabecera(token_de(client, "jefe@uni.edu")),
    }


def csv_df(texto: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(texto))


# ------------------------------------------------------------------ permisos
@pytest.mark.parametrize("ruta", ["/reportes", "/reportes/exportar"])
def test_permisos_por_rol(client, db, ruta):
    h = tokens(client, db)
    assert client.get(f"{API}{ruta}").status_code == 401
    r = client.get(f"{API}{ruta}", headers=h["estudiante"])
    assert r.status_code == 403 and r.json()["error"] is True
    assert client.get(f"{API}{ruta}", headers=h["docente"]).status_code == 200
    assert client.get(f"{API}{ruta}", headers=h["administrador"]).status_code == 200


def test_el_estudiante_no_recibe_ni_un_dato(client, db, mundo):
    h = tokens(client, db)
    for ruta in ("/reportes", "/reportes/exportar?tipo=intentos", "/reportes/exportar?tipo=todos"):
        r = client.get(f"{API}{ruta}", headers=h["estudiante"])
        assert r.status_code == 403 and "filtrado" not in r.text


# ------------------------------------------------------------------ privacidad
def test_ninguna_salida_contiene_nombre_ni_correo(client, db, mundo):
    h = tokens(client, db)["docente"]
    salidas = [client.get(f"{API}/reportes", headers=h).text]
    for tipo in ("intentos", "ayudas", "cambios_ns", "indicadores"):
        r = client.get(f"{API}/reportes/exportar?tipo={tipo}", headers=h)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        salidas.append(r.text)
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{API}/reportes/exportar?tipo=todos", headers=h).content))
    salidas += [z.read(n).decode("utf-8") for n in z.namelist()]
    assert len(salidas) == 9
    for texto in salidas:
        bajo = texto.lower()
        for f in FRAGMENTOS_PERSONALES:
            assert f not in bajo, f"la salida contiene «{f}»"
    for nombre, correo in PERSONAS:  # y los datos del staff que consulta
        assert nombre not in "".join(salidas) and correo not in "".join(salidas)


def test_la_exportacion_se_detiene_si_se_colara_un_dato_personal():
    from app.modules.analitica.exportacion import verificar_sin_datos_personales

    with pytest.raises(ValueError):
        verificar_sin_datos_personales(pd.DataFrame({"id_pseudonimo": ["a"], "correo": ["x@y.z"]}))
    with pytest.raises(ValueError):
        verificar_sin_datos_personales(pd.DataFrame({"id_pseudonimo": ["a"], "proveedor": ["ana@uni.edu"]}))
    with pytest.raises(ValueError):
        verificar_sin_datos_personales(pd.DataFrame({"usuario_id": [1]}))
    verificar_sin_datos_personales(pd.DataFrame({"id_pseudonimo": ["a"], "proveedor": ["mock"]}))


def test_el_reporte_no_trae_filas_por_estudiante(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    assert "por_estudiante" not in json.dumps(j) and "id_pseudonimo" not in json.dumps(j) and "usuario" not in json.dumps(j)


# ------------------------------------------------------------------ supresión de celdas pequeñas
def test_n_minimo_esta_en_reglas_json_como_provisional():
    cfg = cargar_reglas()["reportes"]
    assert cfg["n_minimo"] == 3 and cfg["provisional"] is True


def test_un_grupo_con_menos_de_n_minimo_no_se_muestra(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    assert j["n_minimo"] == 3
    des = {(f["concepto"], f["dificultad"]): f for f in j["desempeno"]}
    visible = des[("filtrado", mundo.desafio("filtrado").dificultad)]
    oculto = des[("join", mundo.desafio("join").dificultad)]
    assert visible["suprimido"] is False and visible["n_estudiantes"] == 4
    assert oculto["suprimido"] is True and all(oculto[k] is None for k in ("n_estudiantes", "n_desafios", "tasa_sa", "intentos_medios", "tr_mediana"))
    ns = {f["concepto"]: f for f in j["distribucion_ns"]}
    assert ns["filtrado"]["suprimido"] is False and ns["join"]["suprimido"] is True and ns["join"]["ns0"] is None
    ay = {f["tipo"]: f for f in j["ayudas"]}
    assert ay["AY2"]["suprimido"] is True and ay["AY2"]["n_solicitudes"] is None
    assert ay["AY3"]["suprimido"] is False and ay["AY3"]["n_solicitudes"] == 0  # vacío ≠ pequeño: un cero no identifica a nadie
    r910 = {f["regla"]: f for f in j["eficacia"]["activacion_r9_r10"]}
    assert r910["R9"]["suprimido"] is False and r910["R10"]["suprimido"] is True
    rr = {(f["concepto"], f["tipo"]): f for f in j["retiros_refuerzos"]}
    assert rr[("filtrado", "retiro")]["suprimido"] is False
    assert rr[("filtrado", "recaida")]["suprimido"] is True and rr[("join", "refuerzo")]["suprimido"] is True
    assert {f["concepto"]: f["suprimido"] for f in j["linea_base"]["por_concepto"]} == {"filtrado": False, "join": True}


def test_la_semana_con_menos_de_n_minimo_estudiantes_se_suprime(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    semanas = {f["semana"]: f for f in j["uso"]}
    assert set(semanas) == {"2026-10-05", "2026-10-12"}
    s1, s2 = semanas["2026-10-05"], semanas["2026-10-12"]
    assert (s1["estudiantes_activos"], s1["sesiones"], s1["intentos"], s1["suprimido"]) == (4, 13, 16, False)
    assert s2["suprimido"] is True and s2["estudiantes_activos"] is None and s2["sesiones"] is None and s2["intentos"] is None
    assert j["resumen"] == {"estudiantes_activos": 4, "suprimido": False}


def test_no_hay_totales_que_permitan_recuperar_una_celda_suprimida(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    assert set(j["resumen"]) == {"estudiantes_activos", "suprimido"}  # solo el distinto de estudiantes, no sumas de grupos
    assert "total" not in json.dumps({k: v for k, v in j.items() if k != "nota_privacidad"}).lower()


def test_n_minimo_se_toma_de_reglas_y_nunca_baja_de_2(monkeypatch):
    assert service.n_minimo({"reportes": {"n_minimo": 5}}) == 5
    assert service.n_minimo({}) == 3  # sin la clave se aplica el valor por defecto
    assert service.n_minimo({"reportes": {"n_minimo": 0}}) == 2  # un grupo de 1 siempre es identificable
    assert service.n_minimo({"reportes": {"n_minimo": "tres"}}) == 3


def test_con_otro_n_minimo_cambia_lo_que_se_muestra(client, db, mundo, monkeypatch):
    reglas = {**cargar_reglas(), "reportes": {"n_minimo": 2}}
    monkeypatch.setattr(service, "cargar_reglas", lambda: reglas)
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    assert j["n_minimo"] == 2
    assert {f["concepto"]: f["suprimido"] for f in j["distribucion_ns"]}["join"] is False  # 2 estudiantes ya alcanzan
    assert {f["regla"]: f["suprimido"] for f in j["eficacia"]["activacion_r9_r10"]}["R10"] is True  # 1 sigue por debajo


def test_funciones_de_supresion():
    assert [calc.pequeno(n, 3) for n in (0, 1, 2, 3, 4)] == [False, True, True, False, False]
    assert [calc.tipo_de_cambio(r, a, n, ("R1", "R2")) for r, a, n in (("R1", 2, 1), ("R2", 1, 0), ("R3", 0, 1), ("R5", 1, 2), ("R14", 0, 1), ("R12", 0, 1), ("R1", 1, 1))] == [
        "retiro", "retiro", "recaida", "refuerzo", "refuerzo", "refuerzo", "otro",
    ]


# ------------------------------------------------------------------ cifras
def test_desempeno_por_concepto_y_dificultad(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    f = next(x for x in j["desempeno"] if x["concepto"] == "filtrado")
    # 12 cierres: SA 9, CP 1, CE 1, NR 1; envíos: 9 SA×1 + CP×1 + CE×3 + NR×2 = 15 → 1.25
    assert (f["n_desafios"], f["tasa_sa"], f["tasa_cp"], f["tasa_ce"], f["tasa_nr"]) == (12, 0.75, 0.0833, 0.0833, 0.0833)
    assert f["intentos_medios"] == 1.25 and f["tr_mediana"] == 1.0
    assert [c["codigo"] for c in j["conceptos"]][:3] == ["filtrado", "ordenamiento", "conteo_agregacion"]


def test_distribucion_de_ns_sale_de_agregados(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    f = next(x for x in j["distribucion_ns"] if x["concepto"] == "filtrado")
    assert (f["n_estudiantes"], f["ns0"], f["ns1"], f["ns2"], f["ns3"]) == (4, 3, 1, 0, 0)


def test_ayudas_por_tipo_y_valoraciones(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    a = next(x for x in j["ayudas"] if x["tipo"] == "AY1")
    assert (a["n_solicitudes"], a["n_estudiantes"], a["n_mostradas_solas"], a["n_valoradas"], a["utiles"], a["no_utiles"], a["proporcion_util"]) == (3, 3, 1, 3, 2, 1, 0.6667)


def test_retiros_y_refuerzos(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    retiro = next(x for x in j["retiros_refuerzos"] if (x["concepto"], x["tipo"]) == ("filtrado", "retiro"))
    assert (retiro["n_cambios"], retiro["n_estudiantes"], retiro["reglas"]) == (3, 3, {"R1": 1, "R2": 2})


def test_linea_base_m_medio(client, db, mundo):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()
    lb = j["linea_base"]
    assert lb["n_estudiantes"] == 4 and lb["m_global_media"] == 0.5
    assert next(x for x in lb["por_concepto"] if x["concepto"] == "filtrado")["m_media"] == 0.45


def test_eficacia_del_retiro(client, db, mundo):
    e = client.get(f"{API}/reportes", headers=tokens(client, db)["docente"]).json()["eficacia"]
    assert e["ns0_sin_recaida"] == {"n_conceptos": 3, "n_estudiantes": 3, "sin_recaida": 2, "proporcion": 0.6667, "suprimido": False}
    d = e["desafios_hasta_primer_retiro"]["global"]
    assert (d["n_conceptos"], d["media"], d["mediana"], d["minimo"], d["maximo"]) == (3, 3.0, 3.0, 3.0, 3.0)
    assert [x["concepto"] for x in e["desafios_hasta_primer_retiro"]["por_concepto"]] == ["filtrado"]
    (bloque,) = e["sa_por_bloque"]  # 14 cierres de 4 estudiantes, todos dentro de los primeros 5 de cada uno
    assert (bloque["desde_orden"], bloque["hasta_orden"], bloque["n_estudiantes"], bloque["n_desafios"], bloque["proporcion_sa"]) == (1, 5, 4, 14, 0.7143)
    r9 = next(x for x in e["activacion_r9_r10"] if x["regla"] == "R9")
    assert (r9["n_activaciones"], r9["n_estudiantes"], r9["n_sesiones"], r9["proporcion_sesiones"]) == (3, 3, 3, 0.2143)
    p = e["precision_ns_inicial"]  # E1-E3 bajaron el NS al 3.er cierre; E4 sin cambios; E1-join subió con R5
    assert (p["n_conceptos"], p["n_estudiantes"], p["coincide"], p["inicial_alto"], p["inicial_bajo"], p["proporcion_coincide"]) == (5, 4, 1, 3, 1, 0.2)


def test_el_filtro_de_fechas_recorta_el_reporte(client, db, mundo):
    h = tokens(client, db)["docente"]
    j = client.get(f"{API}/reportes?desde=2026-10-12&hasta=2026-10-18", headers=h).json()
    assert [f["semana"] for f in j["uso"]] == ["2026-10-12"] and j["uso"][0]["suprimido"] is True
    assert all(f["suprimido"] for f in j["desempeno"]) and j["periodo"]["desde"].startswith("2026-10-12")
    assert j["eficacia"]["ns0_sin_recaida"]["n_conceptos"] == 0  # las llegadas a NS 0 fueron en la semana 1


def test_reporte_sin_datos_responde_con_tablas_vacias(client, db):
    j = client.get(f"{API}/reportes", headers=tokens(client, db)["administrador"]).json()
    assert j["uso"] == [] and j["desempeno"] == [] and j["distribucion_ns"] == [] and j["retiros_refuerzos"] == []
    assert j["resumen"] == {"estudiantes_activos": 0, "suprimido": False}  # cero no identifica a nadie: se muestra
    assert j["eficacia"]["precision_ns_inicial"]["n_conceptos"] == 0 and len(j["ayudas"]) == 4


@pytest.mark.parametrize("consulta", ["desde=hoy", "desde=2026-12-01&hasta=2026-01-01", "hasta=2026-13-45"])
def test_fechas_invalidas_dan_422_en_espanol(client, db, consulta):
    h = tokens(client, db)["docente"]
    for ruta in ("/reportes", "/reportes/exportar"):
        r = client.get(f"{API}{ruta}?{consulta}", headers=h)
        assert r.status_code == 422 and r.json()["error"] is True and "fecha" in r.json()["mensaje"].lower()


# ------------------------------------------------------------------ exportación
def test_cada_csv_tiene_sus_columnas_y_filas(client, db, mundo):
    h = tokens(client, db)["docente"]
    esperado = {"intentos": (17, 7), "ayudas": (4, 12), "cambios_ns": (5, 6), "indicadores": (14, 10)}
    for tipo, (filas, columnas) in esperado.items():
        r = client.get(f"{API}/reportes/exportar?tipo={tipo}", headers=h)
        assert r.headers["content-disposition"].startswith("attachment; filename=") and tipo in r.headers["content-disposition"]
        assert r.headers["cache-control"] == "no-store"
        df = csv_df(r.text)
        assert (len(df), len(df.columns)) == (filas, columnas), tipo
        assert df.columns[0] == "id_pseudonimo" and not {"usuario_id", "nombre", "correo", "codigo"} & set(df.columns)
    assert client.get(f"{API}/reportes/exportar", headers=h).text.splitlines()[0].startswith("id_pseudonimo,sesion_id")  # por defecto: intentos


def test_el_seudonimo_es_el_mismo_en_todos_los_csv_y_coincide_con_el_hmac(client, db, mundo):
    h = tokens(client, db)["docente"]
    esperados = {id_pseudonimo(u.id) for u in mundo.usuarios}
    for tipo in ("intentos", "ayudas", "cambios_ns", "indicadores"):
        ids = set(csv_df(client.get(f"{API}/reportes/exportar?tipo={tipo}", headers=h).text)["id_pseudonimo"])
        assert ids <= esperados and all(re.fullmatch(r"[0-9a-f]{16}", i) for i in ids)
    assert len({id_pseudonimo(u.id) for u in mundo.usuarios}) == 4


def test_la_exportacion_respeta_el_filtro_de_fechas(client, db, mundo):
    h = tokens(client, db)["docente"]
    df = csv_df(client.get(f"{API}/reportes/exportar?tipo=intentos&desde=2026-10-12", headers=h).text)
    assert len(df) == 1 and df["creado_en"][0].startswith("2026-10-13")
    assert len(csv_df(client.get(f"{API}/reportes/exportar?tipo=cambios_ns&hasta=2026-10-07", headers=h).text)) == 3


def test_las_ayudas_exportadas_no_llevan_el_texto(client, db, mundo):
    r = client.get(f"{API}/reportes/exportar?tipo=ayudas", headers=tokens(client, db)["docente"])
    assert "Texto de la ayuda" not in r.text and "SELECT" not in r.text
    df = csv_df(r.text)
    assert sorted(df["tipo_ayuda"]) == ["AY1", "AY1", "AY1", "AY2"] and df["valoracion"].tolist().count(1) == 3


def test_exportar_todo_en_zip(client, db, mundo):
    r = client.get(f"{API}/reportes/exportar?tipo=todos", headers=tokens(client, db)["administrador"])
    assert r.headers["content-type"] == "application/zip" and ".zip" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(n.split("_")[0] if not n.startswith("cambios") else "cambios_ns" for n in z.namelist()) == ["ayudas", "cambios_ns", "indicadores", "intentos"]


def test_tipo_de_exportacion_invalido_da_422(client, db):
    r = client.get(f"{API}/reportes/exportar?tipo=usuarios", headers=tokens(client, db)["docente"])
    assert r.status_code == 422 and r.json()["error"] is True and "intentos" in r.json()["mensaje"]


def test_la_exportacion_queda_auditada_sin_datos_personales(client, db, mundo):
    h = tokens(client, db)
    client.get(f"{API}/reportes/exportar?tipo=intentos&desde=2026-10-01", headers=h["docente"])
    client.get(f"{API}/reportes/exportar?tipo=todos", headers=h["administrador"])
    client.get(f"{API}/reportes/exportar?tipo=intentos", headers=h["estudiante"])  # 403: no se audita
    db.expire_all()
    filas = list(db.scalars(select(Auditoria).where(Auditoria.accion == "reporte.exportar").order_by(Auditoria.id)))
    assert [f.objeto for f in filas] == ["reporte:intentos", "reporte:todos"]
    assert filas[0].detalle["filas"] == {"intentos": 17} and filas[0].detalle["desde"].startswith("2026-10-01")
    assert set(filas[1].detalle["filas"]) == {"intentos", "ayudas", "cambios_ns", "indicadores"}
    assert "@" not in json.dumps([f.detalle for f in filas])


def test_el_script_exporta_lo_mismo_que_el_endpoint(client, db, mundo, tmp_path):
    entorno = {**os.environ, "ANON_SALT": "sal-de-prueba", "PYTHONUTF8": "1"}
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "exportar_tesis.py"), "--salida", str(tmp_path), "--desde", "2026-10-01"],
        capture_output=True, text=True, env=entorno, cwd=RAIZ,
    )
    assert r.returncode == 0, r.stderr
    archivos = sorted(p.name for p in tmp_path.iterdir())
    assert len(archivos) == 4 and all(a.endswith("_20261001_hoy.csv") for a in archivos)
    df = csv_df((tmp_path / "intentos_20261001_hoy.csv").read_text(encoding="utf-8"))
    assert len(df) == 17 and set(df["id_pseudonimo"]) == {id_pseudonimo(u.id, "sal-de-prueba") for u in mundo.usuarios}
    for p in tmp_path.iterdir():
        texto = p.read_text(encoding="utf-8").lower()
        assert not any(f in texto for f in FRAGMENTOS_PERSONALES)
    assert "ANON_SALT" not in r.stderr  # con sal definida no hay aviso


def test_el_script_avisa_si_falta_la_sal_y_rechaza_fechas_malas(client, tmp_path):
    base = [sys.executable, str(RAIZ / "scripts" / "exportar_tesis.py")]
    entorno = {**os.environ, "ANON_SALT": "", "PYTHONUTF8": "1"}
    r = subprocess.run(base + ["--salida", str(tmp_path), "--tipo", "intentos"], capture_output=True, text=True, env=entorno, cwd=RAIZ)
    assert r.returncode == 0 and "ANON_SALT" in r.stderr and len(list(tmp_path.iterdir())) == 1
    r = subprocess.run(base + ["--desde", "ayer", "--salida", str(tmp_path)], capture_output=True, text=True, env=entorno, cwd=RAIZ)
    assert r.returncode == 2 and "fecha" in r.stderr.lower()
