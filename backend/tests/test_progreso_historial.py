"""Entrega 11: GET /progreso/intentos (RF-24) y GET /progreso/evolucion (RF-23)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.seguridad import hashear_password
from app.modules.analitica.models import IndicadorHistorico
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Desafio, Intento, SesionDesafio
from app.modules.motor_retiro.models import HistorialNivel
from conftest import API, cabecera, registrar, token_de
from test_desafios import SOLUCION, crear_desafio
from test_motor_integracion import abandonar, ana, concepto, preparar

URL_INTENTOS = f"{API}/progreso/intentos"
URL_EVOLUCION = f"{API}/progreso/evolucion"
MALO = "SELECT titulo FROM libros"  # corre, pero no es la solución


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def enviar(client, h, did, codigo=MALO):
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": codigo}, headers=h)


def fechar_intentos(db, fechas: list[datetime], sesion_id: int | None = None):
    """Pone `fechas` a los intentos (en orden de id) de una sesión, o de todos si no se indica."""
    consulta = select(Intento).order_by(Intento.id)
    if sesion_id is not None:
        consulta = consulta.where(Intento.sesion_id == sesion_id)
    for intento, f in zip(db.scalars(consulta).all(), fechas, strict=True):
        intento.creado_en = f
    db.commit()


# ---------- Permisos y datos propios ----------
@pytest.mark.parametrize("url", [URL_INTENTOS, URL_EVOLUCION])
def test_requieren_sesion_y_rol_estudiante(client, db, url):
    assert client.get(url).status_code == 401
    db.add(Usuario(nombre="Profe", correo="profe@uni.edu", rol=Rol.docente.value, hash_password=hashear_password("Clave12345")))
    db.commit()
    token = token_de(client, "profe@uni.edu", "Clave12345")
    assert client.get(url, headers=cabecera(token)).status_code == 403


def test_intentos_solo_datos_propios_y_sin_codigo_del_estudiante(client, db):
    h, did = preparar(client, db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    enviar(client, h, did, "SELECT 'MI_CODIGO_PRIVADO' AS x")
    registrar(client, "Otra", "otra@uni.edu")
    h2 = cabecera(token_de(client, "otra@uni.edu"))

    propio = client.get(URL_INTENTOS, headers=h)
    assert propio.status_code == 200 and propio.json()["total"] == 1
    assert "MI_CODIGO_PRIVADO" not in propio.text and "codigo" not in propio.json()["intentos"][0]

    ajeno = client.get(URL_INTENTOS, headers=h2).json()
    assert ajeno["total"] == 0 and ajeno["intentos"] == [] and ajeno["desafios"] == []
    # filtrar por el desafío de otra persona tampoco filtra nada de ella
    assert client.get(URL_INTENTOS, params={"desafio_id": did}, headers=h2).json()["total"] == 0


def test_evolucion_solo_datos_propios(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        abandonar(client, h, did)
    registrar(client, "Otra", "otra@uni.edu")
    j = client.get(URL_EVOLUCION, headers=cabecera(token_de(client, "otra@uni.edu"))).json()
    assert j["indicadores"] == [] and j["cambios_ns"] == [] and j["conceptos_con_datos"] == []


# ---------- Historial de intentos ----------
def test_sin_intentos_estado_vacio(client):
    registrar(client)
    j = client.get(URL_INTENTOS, headers=cabecera(token_de(client))).json()
    assert j["intentos"] == [] and j["total"] == 0 and j["pagina"] == 1 and j["paginas"] == 1 and j["desafios"] == []


def test_lista_los_intentos_mas_recientes_primero_con_resultado_legible(client, db):
    h, did = preparar(client, db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    enviar(client, h, did, MALO)
    enviar(client, h, did, "SELECT columna_inexistente FROM libros")
    enviar(client, h, did, SOLUCION)
    fechar_intentos(db, [utc(2026, 3, 1, 10), utc(2026, 3, 1, 11), utc(2026, 3, 1, 12)])
    j = client.get(URL_INTENTOS, headers=h).json()
    assert [i["numero"] for i in j["intentos"]] == [3, 2, 1]
    assert [i["correcto"] for i in j["intentos"]] == [True, False, False]
    primero = j["intentos"][0]
    assert primero["resultado"] == "Correcto" and primero["desafio"] == "Libros recientes"
    assert primero["concepto"] == "Filtrado (WHERE)" and primero["dificultad"] == "D1"
    assert j["intentos"][2]["resultado"] == "Resultado distinto al esperado"
    assert j["intentos"][1]["resultado"] == "Error de SQL"
    assert "detalle_tecnico" not in client.get(URL_INTENTOS, headers=h).text


def test_filtro_por_desafio_y_opciones_del_selector(client, db):
    h, d1 = preparar(client, db)
    d2 = crear_desafio(db, "ordenamiento", titulo="Libros por año")
    for did in (d1, d1, d2):
        client.post(f"{API}/desafios/{did}/iniciar", headers=h)
        enviar(client, h, did)
    j = client.get(URL_INTENTOS, params={"desafio_id": d2}, headers=h).json()
    assert j["total"] == 1 and j["intentos"][0]["desafio_id"] == d2
    # las opciones del selector no dependen del filtro
    assert [o["titulo"] for o in j["desafios"]] == ["Libros por año", "Libros recientes"]
    assert client.get(URL_INTENTOS, headers=h).json()["total"] == 3


def test_filtro_por_rango_de_fechas_incluye_el_ultimo_dia_completo(client, db):
    h, did = preparar(client, db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    for _ in range(4):
        enviar(client, h, did)
    fechar_intentos(db, [utc(2026, 3, 9, 23, 59), utc(2026, 3, 10, 0, 0), utc(2026, 3, 10, 18, 30), utc(2026, 3, 11, 0, 1)])

    def numeros(**p):
        return sorted(i["numero"] for i in client.get(URL_INTENTOS, params=p, headers=h).json()["intentos"])

    assert numeros(desde="2026-03-10", hasta="2026-03-10") == [2, 3]  # el día entero, ambos extremos
    assert numeros(desde="2026-03-10") == [2, 3, 4]
    assert numeros(hasta="2026-03-09") == [1]
    assert numeros(desde="2026-03-10T12:00:00Z", hasta="2026-03-10T23:00:00+00:00") == [3]
    assert numeros(desde="2026-03-10T00:00:00-05:00", hasta="2026-03-10") == [3]  # 00:00 en UTC-5 = 05:00 UTC
    assert numeros(desde="", hasta="") == [1, 2, 3, 4]  # vacíos = sin filtro


def test_filtros_combinados_desafio_y_fechas(client, db):
    h, d1 = preparar(client, db)
    d2 = crear_desafio(db, "ordenamiento", titulo="Libros por año")
    for did in (d1, d2):
        client.post(f"{API}/desafios/{did}/iniciar", headers=h)
        enviar(client, h, did)
        enviar(client, h, did)
    fechar_intentos(db, [utc(2026, 5, 1), utc(2026, 5, 20), utc(2026, 5, 2), utc(2026, 5, 21)])  # d1: 1 y 20; d2: 2 y 21
    j = client.get(URL_INTENTOS, params={"desafio_id": d1, "desde": "2026-05-15", "hasta": "2026-05-31"}, headers=h).json()
    assert j["total"] == 1 and j["intentos"][0]["desafio_id"] == d1 and j["intentos"][0]["numero"] == 2


def test_rango_vacio_responde_200_sin_filas(client, db):
    h, did = preparar(client, db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    enviar(client, h, did)
    r = client.get(URL_INTENTOS, params={"desde": "2001-01-01", "hasta": "2001-12-31"}, headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 0 and j["intentos"] == [] and j["paginas"] == 1
    assert len(j["desafios"]) == 1  # el selector sigue ofreciendo sus desafíos


def test_paginacion(client, db):
    h, did = preparar(client, db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    for _ in range(5):
        enviar(client, h, did)
    fechar_intentos(db, [utc(2026, 4, d) for d in range(1, 6)])

    def pagina(n, tam=2):
        return client.get(URL_INTENTOS, params={"pagina": n, "tam": tam}, headers=h).json()

    p1, p2, p3, p4 = pagina(1), pagina(2), pagina(3), pagina(4)
    assert (p1["total"], p1["paginas"], p1["tam"], p1["pagina"]) == (5, 3, 2, 1)
    assert [i["numero"] for i in p1["intentos"]] == [5, 4]
    assert [i["numero"] for i in p2["intentos"]] == [3, 2]
    assert [i["numero"] for i in p3["intentos"]] == [1]
    assert p4["intentos"] == [] and p4["total"] == 5  # más allá de la última página: vacío, no error
    assert len({i["id"] for p in (p1, p2, p3) for i in p["intentos"]}) == 5  # sin repetidos ni saltos
    assert client.get(URL_INTENTOS, headers=h).json()["tam"] == 20  # valor por defecto


@pytest.mark.parametrize("params", [{"pagina": 0}, {"tam": 0}, {"tam": 101}, {"pagina": "x"}, {"desafio_id": "abc"}, {"desafio_id": 0}])
def test_paginacion_invalida_422(client, params):
    registrar(client)
    r = client.get(URL_INTENTOS, params=params, headers=cabecera(token_de(client)))
    assert r.status_code == 422 and r.json()["error"] is True and r.json()["mensaje"].startswith("Revisa los datos")


@pytest.mark.parametrize("url", [URL_INTENTOS, URL_EVOLUCION])
@pytest.mark.parametrize(
    "params, campo",
    [
        ({"desde": "ayer"}, "desde"),
        ({"hasta": "31/12/2026"}, "hasta"),
        ({"desde": "2026-02-30"}, "desde"),
        ({"hasta": "2026-13-01"}, "hasta"),
        ({"desde": "2026-03-10T25:00:00"}, "desde"),
    ],
)
def test_fecha_invalida_422_con_mensaje_amable(client, url, params, campo):
    registrar(client)
    r = client.get(url, params=params, headers=cabecera(token_de(client)))
    j = r.json()
    assert r.status_code == 422 and j["error"] is True
    assert "AAAA-MM-DD" in j["mensaje"] and "Traceback" not in r.text and "ValueError" not in r.text
    assert j["detalles"][0]["campo"] == campo


@pytest.mark.parametrize("url", [URL_INTENTOS, URL_EVOLUCION])
def test_rango_invertido_422(client, url):
    registrar(client)
    r = client.get(url, params={"desde": "2026-03-10", "hasta": "2026-03-01"}, headers=cabecera(token_de(client)))
    assert r.status_code == 422 and "no puede ser posterior" in r.json()["mensaje"]


# ---------- Evolución ----------
def test_evolucion_sin_historial_esta_vacia(client):
    registrar(client)
    j = client.get(URL_EVOLUCION, headers=cabecera(token_de(client))).json()
    assert j == {"concepto": None, "indicadores": [], "cambios_ns": [], "conceptos_con_datos": []}


def test_evolucion_series_de_indicadores_y_linea_de_tiempo_del_ns(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        abandonar(client, h, did)  # 3 cierres; el tercero activa R5 (NS 1 → 2)
    j = client.get(URL_EVOLUCION, headers=h).json()
    assert [p["n_ventana"] for p in j["indicadores"]] == [1, 2, 3]
    assert [p["ns"] for p in j["indicadores"]] == [1, 1, 2]
    p = j["indicadores"][0]
    assert p["concepto"] == "filtrado" and p["concepto_nombre"] == "Filtrado (WHERE)"
    assert p["ta"] == 0.0 and p["ua"] == 0.0 and {"ta", "ni", "tr", "ua", "fecha", "sesion_id"} <= set(p)
    assert len(j["cambios_ns"]) == 1
    c = j["cambios_ns"][0]
    assert (c["ns_anterior"], c["ns_nuevo"], c["concepto"]) == (1, 2, "filtrado")
    assert "R5" not in c["texto"] and "regla" not in c  # texto del estudiante, no el motivo técnico
    assert j["conceptos_con_datos"] == [{"codigo": "filtrado", "nombre": "Filtrado (WHERE)"}]


def test_evolucion_filtra_por_concepto(client, db):
    h, d1 = preparar(client, db)
    d2 = crear_desafio(db, "ordenamiento", titulo="Libros por año")
    abandonar(client, h, d1)
    abandonar(client, h, d2)
    todo = client.get(URL_EVOLUCION, headers=h).json()
    assert {p["concepto"] for p in todo["indicadores"]} == {"filtrado", "ordenamiento"} and todo["concepto"] is None
    solo = client.get(URL_EVOLUCION, params={"concepto": "ordenamiento"}, headers=h).json()
    assert solo["concepto"] == "ordenamiento" and {p["concepto"] for p in solo["indicadores"]} == {"ordenamiento"}
    # las opciones del selector no dependen del filtro
    assert {c["codigo"] for c in solo["conceptos_con_datos"]} == {"filtrado", "ordenamiento"}


def test_evolucion_concepto_inexistente_404_amable(client):
    registrar(client)
    r = client.get(URL_EVOLUCION, params={"concepto": "no_existe"}, headers=cabecera(token_de(client)))
    assert r.status_code == 404 and r.json()["mensaje"] == "No encontramos ese concepto."


def test_evolucion_rango_de_fechas_y_rango_vacio(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        abandonar(client, h, did)
    filas = list(db.scalars(select(IndicadorHistorico).order_by(IndicadorHistorico.id)))
    for f, fecha in zip(filas, [utc(2026, 6, 1, 9), utc(2026, 6, 10, 9), utc(2026, 6, 20, 9)], strict=True):
        f.creado_en = fecha
    h_niv = db.scalar(select(HistorialNivel))
    h_niv.creado_en = utc(2026, 6, 20, 9)
    db.commit()

    j = client.get(URL_EVOLUCION, params={"desde": "2026-06-05", "hasta": "2026-06-30"}, headers=h).json()
    assert [p["n_ventana"] for p in j["indicadores"]] == [2, 3] and len(j["cambios_ns"]) == 1
    j = client.get(URL_EVOLUCION, params={"desde": "2026-06-01", "hasta": "2026-06-10"}, headers=h).json()
    assert [p["n_ventana"] for p in j["indicadores"]] == [1, 2] and j["cambios_ns"] == []  # el cambio es del día 20

    vacio = client.get(URL_EVOLUCION, params={"desde": "2001-01-01", "hasta": "2001-02-01"}, headers=h)
    assert vacio.status_code == 200
    assert vacio.json()["indicadores"] == [] and vacio.json()["cambios_ns"] == []
    assert len(vacio.json()["conceptos_con_datos"]) == 1  # el selector sigue ofreciendo sus conceptos


def test_evolucion_acepta_indicadores_nulos(client, db):
    h, did = preparar(client, db)
    abandonar(client, h, did)
    fila = db.scalar(select(IndicadorHistorico))
    fila.ta = fila.ni = fila.tr = fila.ua = None
    db.commit()
    p = client.get(URL_EVOLUCION, headers=h).json()["indicadores"][0]
    assert p["ta"] is None and p["ni"] is None and p["tr"] is None and p["ua"] is None


def test_errores_de_base_responden_503_controlado(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.modules.progreso import service

    registrar(client)
    h = cabecera(token_de(client))

    def falla(*a, **k):
        raise OperationalError("SELECT", {}, Exception("detalle interno secreto"))

    monkeypatch.setattr(service, "_intentos", falla)
    monkeypatch.setattr(service, "_evolucion", falla)
    for url in (URL_INTENTOS, URL_EVOLUCION):
        r = client.get(url, headers=h)
        assert r.status_code == 503 and r.json()["error"] is True
        assert "secreto" not in r.text and "Inténtalo" in r.json()["mensaje"]
