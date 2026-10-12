import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.db import SessionLocal
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Concepto, Desafio
from app.modules.motor_retiro.models import HistorialNivel
from app.modules.progreso import service
from conftest import API, cabecera, login, registrar, token_de

URL = f"{API}/progreso/resumen"


def estudiante(client):
    registrar(client)
    return cabecera(token_de(client))


def _desafio(db, codigo="filtrado") -> Desafio:
    c = db.scalar(select(Concepto).where(Concepto.codigo == codigo))
    return db.scalar(select(Desafio).where(Desafio.concepto_id == c.id))


def test_requiere_sesion_y_rol_estudiante(client, db):
    assert client.get(URL).status_code == 401
    db.add(
        Usuario(nombre="Profe", correo="profe@uni.edu", rol=Rol.docente.value,
                hash_password=__import__("app.core.seguridad", fromlist=["x"]).hashear_password("Clave12345"))
    )
    db.commit()
    token = token_de(client, "profe@uni.edu", "Clave12345")
    assert client.get(URL, headers=cabecera(token)).status_code == 403


def test_sin_actividad_valores_iniciales_y_sugerencia(client):
    h = estudiante(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["sin_actividad"] is True and "desafío" in j["sugerencia"]
    assert j["desafios_resueltos"] == 0 and j["desafios_disponibles"] == 6
    assert j["ayudas"] == {"AY1": 0, "AY2": 0, "AY3": 0, "AY4": 0, "total": 0}
    assert j["cambios_recientes"] == [] and j["diagnostico_completado"] is False
    assert len(j["niveles"]) == 10 and all(n["ns"] == 1 and n["desafios_resueltos"] == 0 for n in j["niveles"])


def test_refleja_resueltos_ayudas_abandonos_y_cambios(client, db):
    h = estudiante(client)
    d1, d2 = _desafio(db, "filtrado"), _desafio(db, "ordenamiento")
    # d1: un intento incorrecto, una ayuda y luego correcto
    client.post(f"{API}/desafios/{d1.id}/iniciar", headers=h)
    client.post(f"{API}/desafios/{d1.id}/intentos", json={"codigo": "SELECT 1"}, headers=h)
    assert client.post(f"{API}/desafios/{d1.id}/ayuda", json={}, headers=h).status_code == 200
    r = client.post(f"{API}/desafios/{d1.id}/intentos", json={"codigo": d1.solucion_referencia}, headers=h)
    assert r.json()["desafio_resuelto"] is True
    # d2: se abandona
    client.post(f"{API}/desafios/{d2.id}/iniciar", headers=h)
    client.post(f"{API}/desafios/{d2.id}/abandonar", headers=h)
    # un cambio de nivel registrado por el motor
    uid = db.scalar(select(Usuario.id).where(Usuario.correo == "ana@uni.edu"))
    db.add(HistorialNivel(usuario_id=uid, concepto_id=d1.concepto_id, ns_anterior=1, ns_nuevo=0, regla="R1", motivo="R1 técnico"))
    db.commit()

    j = client.get(URL, headers=h).json()
    assert j["sin_actividad"] is False and j["sugerencia"] is None
    assert j["desafios_resueltos"] == 1 and j["sesiones_abandonadas"] == 1
    assert j["ayudas"]["total"] == 1 and sum(j["ayudas"][t] for t in ("AY1", "AY2", "AY3", "AY4")) == 1
    filtrado = next(n for n in j["niveles"] if n["codigo"] == "filtrado")
    assert filtrado["desafios_resueltos"] == 1
    c = j["cambios_recientes"][0]
    assert (c["ns_anterior"], c["ns_nuevo"]) == (1, 0) and c["concepto"] == "Filtrado (WHERE)"
    assert "R1" not in c["texto"] and "técnico" not in c["texto"]  # texto del estudiante, no el motivo técnico


def test_no_cuenta_resuelto_con_solucion_mostrada(client, db):
    h = estudiante(client)
    d = _desafio(db)
    client.post(f"{API}/desafios/{d.id}/iniciar", headers=h)
    from app.modules.desafios.models import SesionDesafio

    s = db.scalar(select(SesionDesafio).where(SesionDesafio.desafio_id == d.id))
    s.estado, s.resultado_cierre = "resuelto", "NR"
    db.commit()
    assert client.get(URL, headers=h).json()["desafios_resueltos"] == 0


def test_solo_ve_su_propio_progreso(client, db):
    h = estudiante(client)
    d = _desafio(db)
    client.post(f"{API}/desafios/{d.id}/iniciar", headers=h)
    client.post(f"{API}/desafios/{d.id}/intentos", json={"codigo": d.solucion_referencia}, headers=h)
    registrar(client, "Otra", "otra@uni.edu")
    h2 = cabecera(token_de(client, "otra@uni.edu"))
    j = client.get(URL, headers=h2).json()
    assert j["sin_actividad"] is True and j["desafios_resueltos"] == 0


def test_error_de_base_responde_503_controlado(client, monkeypatch):
    h = estudiante(client)

    def falla(*a, **k):
        raise OperationalError("SELECT", {}, Exception("detalle interno secreto"))

    monkeypatch.setattr(service, "_resumen", falla)
    r = client.get(URL, headers=h)
    assert r.status_code == 503 and r.json()["error"] is True
    assert "secreto" not in r.text and "Inténtalo" in r.json()["mensaje"]


def test_sin_registro_de_ns_usa_defecto_y_con_registro_el_guardado(client, db):
    h = estudiante(client)
    from app.modules.linea_base.models import NivelSoporte

    uid = db.scalar(select(Usuario.id).where(Usuario.correo == "ana@uni.edu"))
    c = db.scalar(select(Concepto).where(Concepto.codigo == "join"))
    db.add(NivelSoporte(usuario_id=uid, concepto_id=c.id, ns=3, ns_maximo_historico=3))
    db.commit()
    niveles = {n["codigo"]: n["ns"] for n in client.get(URL, headers=h).json()["niveles"]}
    assert niveles["join"] == 3 and niveles["filtrado"] == 1
