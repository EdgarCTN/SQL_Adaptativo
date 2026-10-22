from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.core.reglas import cargar_reglas
from app.modules.auth.models import Usuario
from app.modules.desafios import service
from app.modules.desafios.models import Desafio, SesionDesafio
from app.modules.motor_retiro import motor
from conftest import API, cabecera, registrar, token_de
from test_desafios import SOLUCION, crear_desafio


@pytest.fixture(autouse=True)
def _sin_desafios_sembrados(client, db):
    db.execute(delete(Desafio))
    db.commit()


def _preparar(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    did = crear_desafio(db)
    sid = client.post(f"{API}/desafios/{did}/iniciar", headers=h).json()["sesion_id"]
    return h, did, sid


def _sesion(db, sid) -> SesionDesafio:
    db.expire_all()
    return db.get(SesionDesafio, sid)


def _mover_atras(db, sid, segundos, con_latido=True):
    """Simula que pasaron `segundos` desde el inicio (y desde el último latido, si lo hay)."""
    s = db.get(SesionDesafio, sid)
    s.inicio = s.inicio - timedelta(seconds=segundos)
    if con_latido and s.ultimo_latido_en is not None:
        s.ultimo_latido_en = s.ultimo_latido_en - timedelta(seconds=segundos)
    db.commit()


def test_la_clave_nueva_esta_en_reglas_como_provisional():
    cfg = cargar_reglas()["tiempo_activo"]
    assert cfg["hueco_max_seg"] == 45 and cfg["provisional"] is True


def test_latido_suma_si_el_hueco_es_corto(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 10)  # inicio hace 10 s
    r = client.post(f"{API}/desafios/{did}/latido", headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert 9 <= r.json()["tiempo_activo_seg"] <= 12
    s = _sesion(db, sid)
    assert s.tiempo_activo_origen == "latidos" and s.ultimo_latido_en is not None
    antes = s.tiempo_activo_seg
    _mover_atras(db, sid, 15)  # el latido anterior fue hace 15 s
    j = client.post(f"{API}/desafios/{did}/latido", headers=h).json()
    assert antes + 14 <= j["tiempo_activo_seg"] <= antes + 17


def test_un_hueco_largo_no_suma_la_pausa(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 10)
    client.post(f"{API}/desafios/{did}/latido", headers=h)
    antes = _sesion(db, sid).tiempo_activo_seg
    _mover_atras(db, sid, 300)  # 5 minutos sin latidos (pausa)
    j = client.post(f"{API}/desafios/{did}/latido", headers=h).json()
    assert j["tiempo_activo_seg"] == antes  # la pausa no se cuenta
    # y el siguiente latido normal vuelve a sumar desde el último
    _mover_atras(db, sid, 12)
    assert client.post(f"{API}/desafios/{did}/latido", headers=h).json()["tiempo_activo_seg"] >= antes + 11


def test_primer_latido_tras_una_pausa_larga_deja_cero(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 600)  # abrió y se fue 10 minutos
    j = client.post(f"{API}/desafios/{did}/latido", headers=h).json()
    assert j["tiempo_activo_seg"] == 0 and _sesion(db, sid).tiempo_activo_origen == "latidos"


def test_al_cerrar_con_latidos_se_usa_lo_acumulado(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 10)
    client.post(f"{API}/desafios/{did}/latido", headers=h)
    _mover_atras(db, sid, 400, con_latido=False)  # reloj: 400 s desde el inicio; latidos: unos 10 s
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h)
    j = r.json()
    assert j["desafio_resuelto"] is True and j["tiempo_activo_seg"] < 60
    s = _sesion(db, sid)
    assert s.tiempo_activo_seg == j["tiempo_activo_seg"] and s.tiempo_activo_origen == "latidos"
    assert (s.fin - s.inicio).total_seconds() > 300  # el reloj habría dicho otra cosa


def test_sin_latidos_se_usa_fin_menos_inicio(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 200, con_latido=False)
    j = client.post(f"{API}/desafios/{did}/intentos", headers=h, json={"codigo": SOLUCION}).json()
    s = _sesion(db, sid)
    assert s.tiempo_activo_origen == "reloj"
    assert s.tiempo_activo_seg == round((s.fin - s.inicio).total_seconds()) == j["tiempo_activo_seg"]
    assert j["tiempo_activo_seg"] >= 200


def test_abandonar_tambien_respeta_el_origen(client, db):
    h, did, sid = _preparar(client, db)
    _mover_atras(db, sid, 10)
    client.post(f"{API}/desafios/{did}/latido", headers=h)
    _mover_atras(db, sid, 500, con_latido=False)
    j = client.post(f"{API}/desafios/{did}/abandonar", headers=h).json()
    assert j["tiempo_activo_seg"] < 60 and _sesion(db, sid).tiempo_activo_origen == "latidos"


def test_el_motor_lee_el_tiempo_activo_acumulado(client, db, monkeypatch):
    h, did, sid = _preparar(client, db)
    capturado = []
    original = motor.evaluar
    monkeypatch.setattr(motor, "evaluar", lambda ctx: (capturado.append(ctx), original(ctx))[1])
    _mover_atras(db, sid, 10)
    client.post(f"{API}/desafios/{did}/latido", headers=h)
    _mover_atras(db, sid, 400, con_latido=False)
    client.post(f"{API}/desafios/{did}/intentos", headers=h, json={"codigo": SOLUCION})
    s = _sesion(db, sid)
    assert capturado, "el motor no se ejecutó al cerrar"
    assert capturado[-1].cierres_recientes[-1].tiempo_activo_seg == s.tiempo_activo_seg < 60


def test_latido_sin_sesion_en_curso_da_409_controlado(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    did = crear_desafio(db)
    r = client.post(f"{API}/desafios/{did}/latido", headers=h)
    assert r.status_code == 409 and r.json()["error"] is True
    did2 = _preparar_extra(client, db, h)
    client.post(f"{API}/desafios/{did2}/abandonar", headers=h)
    assert client.post(f"{API}/desafios/{did2}/latido", headers=h).status_code == 409


def _preparar_extra(client, db, h):
    did = crear_desafio(db, titulo="Otro desafío")
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    return did


def test_latido_exige_estudiante_y_sesion(client, db):
    did = crear_desafio(db)
    assert client.post(f"{API}/desafios/{did}/latido").status_code == 401
    from app.core.seguridad import hashear_password
    from app.modules.auth.models import Rol

    db.add(Usuario(nombre="Profe", correo="profe@uni.edu", rol=Rol.docente.value, hash_password=hashear_password("Clave12345")))
    db.commit()
    h = cabecera(token_de(client, "profe@uni.edu", "Clave12345"))
    assert client.post(f"{API}/desafios/{did}/latido", headers=h).status_code == 403


def test_sin_umbral_en_reglas_el_latido_no_rompe_y_rige_el_reloj(client, db, monkeypatch):
    h, did, sid = _preparar(client, db)
    monkeypatch.setattr(service, "cargar_reglas", lambda: {})
    r = client.post(f"{API}/desafios/{did}/latido", headers=h)
    assert r.status_code == 200 and _sesion(db, sid).tiempo_activo_origen is None
    j = client.post(f"{API}/desafios/{did}/intentos", headers=h, json={"codigo": SOLUCION}).json()
    assert _sesion(db, sid).tiempo_activo_origen == "reloj" and j["desafio_resuelto"]
