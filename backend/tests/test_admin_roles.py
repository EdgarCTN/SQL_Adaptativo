"""Entrega 13A: administración de roles, activación de cuentas y auditoría."""
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.errores import ErrorApp
from app.core.seguridad import hashear_password
from app.modules.admin import service
from app.modules.admin.auditoria import registrar_auditoria
from app.modules.admin.models import Auditoria
from app.modules.auth.models import Rol, Usuario
from app.seeds.seed import sembrar_administrador
from conftest import API, cabecera, login, registrar, token_de
from test_docente_desafios import payload

RUTA = f"{API}/admin/usuarios"
RUTA_BANCO = f"{API}/docente/desafios"
CLAVE = "Clave12345"


def _usuario(db, rol: Rol, correo: str, nombre: str | None = None, activo: bool = True) -> Usuario:
    u = Usuario(
        nombre=nombre or f"{rol.value.title()} {correo.split('@')[0]}",
        correo=correo,
        rol=rol.value,
        activo=activo,
        hash_password=hashear_password(CLAVE),
    )
    db.add(u)
    db.commit()
    return u


def _sesion(client, db, rol: Rol, correo: str) -> SimpleNamespace:
    u = _usuario(db, rol, correo)
    return SimpleNamespace(id=u.id, correo=correo, h=cabecera(token_de(client, correo, CLAVE)))


@pytest.fixture
def admin(client, db):
    return _sesion(client, db, Rol.administrador, "admin@uni.edu")


@pytest.fixture
def docente(client, db):
    return _sesion(client, db, Rol.docente, "profe@uni.edu")


@pytest.fixture
def estudiante(client, db):
    registrar(client, nombre="Ana Pérez", correo="ana@uni.edu", contrasena=CLAVE)
    h = cabecera(token_de(client, "ana@uni.edu", CLAVE))
    return SimpleNamespace(id=db.scalar(select(Usuario.id).where(Usuario.correo == "ana@uni.edu")), correo="ana@uni.edu", h=h)


def _rol_de(db, usuario_id: int) -> str:
    return db.scalar(select(Usuario.rol).where(Usuario.id == usuario_id))


def _auditoria(db, accion: str | None = None) -> list[Auditoria]:
    db.expire_all()
    consulta = select(Auditoria).order_by(Auditoria.id)
    if accion:
        consulta = consulta.where(Auditoria.accion == accion)
    return list(db.scalars(consulta))


# ---------- Permisos ----------
LLAMADAS_ADMIN = [
    ("get", ""),
    ("put", "/1/rol"),
    ("post", "/1/activar"),
    ("post", "/1/desactivar"),
]


def _llamar(client, metodo: str, sufijo: str, headers=None):
    kw = {"json": {"rol": "docente"}} if metodo in ("put", "post") else {}
    return client.request(metodo.upper(), RUTA + sufijo, headers=headers, **kw)


def test_sin_sesion_401(client):
    for metodo, sufijo in LLAMADAS_ADMIN:
        assert _llamar(client, metodo, sufijo).status_code == 401, f"{metodo} {sufijo}"


@pytest.mark.parametrize("quien", ["estudiante", "docente"])
def test_estudiante_y_docente_reciben_403_en_todas_las_rutas_admin(client, estudiante, docente, db, quien):
    h = (estudiante if quien == "estudiante" else docente).h
    for metodo, sufijo in LLAMADAS_ADMIN:
        r = _llamar(client, metodo, sufijo, h)
        assert r.status_code == 403, f"{quien}: {metodo} {sufijo} dio {r.status_code}"
        assert r.json()["error"] is True and "permiso" in r.json()["mensaje"]
    assert _auditoria(db) == []  # un 403 no deja rastro ni cambia nada


def test_el_administrador_accede(client, admin):
    assert client.get(RUTA, headers=admin.h).status_code == 200


def test_el_administrador_no_usa_las_rutas_de_estudiante(client, admin):
    assert client.get(f"{API}/desafios", headers=admin.h).status_code == 403


# ---------- Listado ----------
def test_lista_paginada_sin_datos_sensibles(client, db, admin):
    for i in range(1, 6):
        _usuario(db, Rol.estudiante, f"est{i}@uni.edu", nombre=f"Estudiante {i}")
    total = db.scalar(select(func.count()).select_from(Usuario))  # 5 + el administrador + el estudiante demo
    paginas = -(-total // 2)
    r = client.get(RUTA, params={"tam": 2}, headers=admin.h)
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == total == 7 and j["tam"] == 2 and j["paginas"] == paginas == 4 and j["pagina"] == 1
    assert len(j["usuarios"]) == 2
    assert set(j["usuarios"][0]) == {"id", "nombre", "correo", "rol", "activo", "creado_en"}
    assert "hash_password" not in r.text and "argon2" not in r.text
    vistos = []
    for pagina in range(1, paginas + 1):
        vistos += [u["id"] for u in client.get(RUTA, params={"tam": 2, "pagina": pagina}, headers=admin.h).json()["usuarios"]]
    assert len(vistos) == total and len(set(vistos)) == total  # sin repetidos ni faltantes


def test_una_pagina_fuera_de_rango_devuelve_la_ultima(client, admin):
    r = client.get(RUTA, params={"pagina": 999999999999}, headers=admin.h)
    assert r.status_code == 200 and r.json()["pagina"] == r.json()["paginas"] == 1
    assert client.get(RUTA, params={"tam": 101}, headers=admin.h).status_code == 422
    assert client.get(RUTA, params={"pagina": 0}, headers=admin.h).status_code == 422


def test_busqueda_por_nombre_y_correo_sin_distinguir_mayusculas(client, db, admin):
    _usuario(db, Rol.estudiante, "lucia.ramos@uni.edu", nombre="Lucía Ramos")
    _usuario(db, Rol.estudiante, "pedro@otro.org", nombre="Pedro Gómez")

    def correos(**params):
        return sorted(u["correo"] for u in client.get(RUTA, params=params, headers=admin.h).json()["usuarios"])

    assert correos(q="RAMOS") == ["lucia.ramos@uni.edu"]
    assert correos(q="otro.org") == ["pedro@otro.org"]
    assert correos(q="  pedro  ") == ["pedro@otro.org"]
    assert correos(q="nadie-se-llama-asi") == []
    assert correos(q="%") == []  # el comodín se trata como texto, no como «todos»


def test_filtro_por_rol(client, db, admin, docente, estudiante):
    assert [u["correo"] for u in client.get(RUTA, params={"rol": "docente"}, headers=admin.h).json()["usuarios"]] == [docente.correo]
    assert client.get(RUTA, params={"rol": "superadmin"}, headers=admin.h).status_code == 422


# ---------- Cambio de rol ----------
def test_convertir_a_un_estudiante_en_docente_le_da_el_banco_de_desafios(client, db, admin, estudiante):
    assert client.get(RUTA_BANCO, headers=estudiante.h).status_code == 403
    r = client.put(f"{RUTA}/{estudiante.id}/rol", json={"rol": "docente"}, headers=admin.h)
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["rol"] == "docente" and "docente" in r.json()["mensaje"]
    assert _rol_de(db, estudiante.id) == "docente"
    # El mismo token ya vale como docente (el rol se lee de la base) y /auth/yo informa el rol nuevo: el menú cambia.
    assert client.get(RUTA_BANCO, headers=estudiante.h).status_code == 200
    assert client.get(f"{API}/auth/yo", headers=estudiante.h).json()["rol"] == "docente"
    assert client.get(f"{API}/desafios", headers=estudiante.h).status_code == 403  # y pierde las rutas de estudiante


def test_se_puede_volver_a_estudiante(client, db, admin, docente):
    r = client.put(f"{RUTA}/{docente.id}/rol", json={"rol": "estudiante"}, headers=admin.h)
    assert r.status_code == 200 and _rol_de(db, docente.id) == "estudiante"
    assert client.get(RUTA_BANCO, headers=docente.h).status_code == 403


def test_nombrar_a_otro_administrador(client, db, admin, docente):
    assert client.put(f"{RUTA}/{docente.id}/rol", json={"rol": "administrador"}, headers=admin.h).status_code == 200
    assert client.get(RUTA, headers=docente.h).status_code == 200


def test_el_mismo_rol_no_cambia_nada_ni_audita(client, db, admin, estudiante):
    r = client.put(f"{RUTA}/{estudiante.id}/rol", json={"rol": "estudiante"}, headers=admin.h)
    assert r.status_code == 200 and "ya tiene" in r.json()["mensaje"]
    assert _auditoria(db) == []


def test_rol_invalido_usuario_inexistente_y_cuerpo_vacio(client, db, admin, estudiante):
    for cuerpo in ({"rol": "superadmin"}, {"rol": ""}, {}):
        r = client.put(f"{RUTA}/{estudiante.id}/rol", json=cuerpo, headers=admin.h)
        assert r.status_code == 422 and r.json()["error"] is True, cuerpo
    assert _rol_de(db, estudiante.id) == "estudiante"
    r = client.put(f"{RUTA}/99999/rol", json={"rol": "docente"}, headers=admin.h)
    assert r.status_code == 404 and "usuario" in r.json()["mensaje"]
    assert client.put(f"{RUTA}/abc/rol", json={"rol": "docente"}, headers=admin.h).status_code == 422
    assert client.put(f"{RUTA}/{10**30}/rol", json={"rol": "docente"}, headers=admin.h).status_code == 422


# ---------- Reglas del último administrador ----------
def test_no_se_puede_cambiar_el_propio_rol(client, db, admin):
    r = client.put(f"{RUTA}/{admin.id}/rol", json={"rol": "docente"}, headers=admin.h)
    assert r.status_code == 409 and "propio rol" in r.json()["mensaje"]
    assert _rol_de(db, admin.id) == "administrador"
    assert client.get(RUTA, headers=admin.h).status_code == 200
    assert _auditoria(db) == []


def test_no_se_puede_desactivar_la_propia_cuenta(client, db, admin):
    r = client.post(f"{RUTA}/{admin.id}/desactivar", headers=admin.h)
    assert r.status_code == 409 and "propia cuenta" in r.json()["mensaje"]
    assert db.scalar(select(Usuario.activo).where(Usuario.id == admin.id)) is True


def test_otro_administrador_si_puede_quitarle_el_rol_y_el_ultimo_queda_protegido(client, db):
    a = _sesion(client, db, Rol.administrador, "a@uni.edu")
    b = _sesion(client, db, Rol.administrador, "b@uni.edu")
    assert client.put(f"{RUTA}/{a.id}/rol", json={"rol": "docente"}, headers=b.h).status_code == 200
    assert _rol_de(db, a.id) == "docente"
    # b es ahora el único administrador: no puede quitarse el rol ni desactivarse.
    assert client.put(f"{RUTA}/{b.id}/rol", json={"rol": "docente"}, headers=b.h).status_code == 409
    assert client.post(f"{RUTA}/{b.id}/desactivar", headers=b.h).status_code == 409
    assert _rol_de(db, b.id) == "administrador"


def test_el_servicio_protege_al_ultimo_administrador_activo(client, db, admin):
    """Defensa en profundidad: aunque quien actúa no sea el propio objetivo, el último administrador activo no cae."""
    actor = SimpleNamespace(id=987654, rol="administrador", activo=True)
    with pytest.raises(ErrorApp) as e:
        service.cambiar_rol(db, actor, admin.id, "docente")
    assert e.value.status_code == 409 and "al menos un administrador" in e.value.mensaje
    with pytest.raises(ErrorApp) as e:
        service.cambiar_activo(db, actor, admin.id, False)
    assert e.value.status_code == 409 and "al menos un administrador" in e.value.mensaje
    assert _rol_de(db, admin.id) == "administrador"
    assert _auditoria(db) == []


def test_un_administrador_inactivo_no_cuenta_como_respaldo(client, db, admin):
    _usuario(db, Rol.administrador, "inactivo@uni.edu", activo=False)
    actor = SimpleNamespace(id=987654, rol="administrador", activo=True)
    with pytest.raises(ErrorApp) as e:
        service.cambiar_rol(db, actor, admin.id, "estudiante")
    assert e.value.status_code == 409
    # En cambio, quitarle el rol a un administrador inactivo está permitido.
    inactivo = db.scalar(select(Usuario).where(Usuario.correo == "inactivo@uni.edu"))
    service.cambiar_rol(db, SimpleNamespace(id=admin.id), inactivo.id, "docente")  # actor real: la auditoría lo referencia
    assert _rol_de(db, inactivo.id) == "docente"


# ---------- Activar y desactivar ----------
def test_desactivar_cierra_el_acceso_y_activar_lo_devuelve(client, db, admin, estudiante):
    r = client.post(f"{RUTA}/{estudiante.id}/desactivar", headers=admin.h)
    assert r.status_code == 200 and r.json()["usuario"]["activo"] is False
    assert client.get(f"{API}/auth/yo", headers=estudiante.h).status_code == 401  # su token deja de valer
    assert login(client, estudiante.correo, CLAVE).status_code == 401
    r = client.post(f"{RUTA}/{estudiante.id}/activar", headers=admin.h)
    assert r.status_code == 200 and r.json()["usuario"]["activo"] is True
    assert login(client, estudiante.correo, CLAVE).status_code == 200
    assert [a.accion for a in _auditoria(db)] == ["usuario.desactivar", "usuario.activar"]


def test_activar_o_desactivar_dos_veces_no_duplica_la_auditoria(client, db, admin, estudiante):
    for _ in range(2):
        assert client.post(f"{RUTA}/{estudiante.id}/desactivar", headers=admin.h).status_code == 200
    assert len(_auditoria(db, "usuario.desactivar")) == 1
    assert client.post(f"{RUTA}/{admin.id}/activar", headers=admin.h).status_code == 200  # ya activa: sin cambios
    assert _auditoria(db, "usuario.activar") == []
    assert client.post(f"{RUTA}/99999/desactivar", headers=admin.h).status_code == 404


# ---------- Auditoría ----------
def test_la_auditoria_registra_el_cambio_de_rol(client, db, admin, estudiante):
    client.put(f"{RUTA}/{estudiante.id}/rol", json={"rol": "docente"}, headers=admin.h)
    filas = _auditoria(db)
    assert len(filas) == 1
    a = filas[0]
    assert a.accion == "usuario.cambiar_rol" and a.usuario_id == admin.id and a.objeto == f"usuario:{estudiante.id}"
    assert a.detalle == {"rol_anterior": "estudiante", "rol_nuevo": "docente"}
    assert a.creado_en is not None
    assert estudiante.correo not in str(a.detalle)  # la auditoría no guarda correos


def test_registrar_auditoria_nunca_rompe_la_accion(client, db, admin):
    registrar_auditoria(db, 999999, "prueba.fk", "x:1")  # usuario inexistente: el guardado falla y se ignora
    assert db.scalar(select(func.count()).select_from(Auditoria)) == 0
    registrar_auditoria(db, admin.id, "prueba.ok", "x:1", {"a": 1})
    assert _auditoria(db)[0].detalle == {"a": 1}


def test_las_acciones_del_docente_sobre_el_banco_se_auditan(client, db, docente):
    r = client.post(RUTA_BANCO, json=payload("Auditoría: novelas"), headers=docente.h)
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert client.put(f"{RUTA_BANCO}/{did}", json=payload("Auditoría: novelas v2"), headers=docente.h).status_code == 200
    assert client.post(f"{RUTA_BANCO}/{did}/desactivar", headers=docente.h).status_code == 200
    assert client.post(f"{RUTA_BANCO}/{did}/activar", headers=docente.h).status_code == 200
    assert client.delete(f"{RUTA_BANCO}/{did}", headers=docente.h).status_code == 200

    filas = _auditoria(db)
    assert [f.accion for f in filas] == [
        "desafio.crear", "desafio.actualizar", "desafio.desactivar", "desafio.activar", "desafio.eliminar",
    ]
    assert all(f.usuario_id == docente.id and f.objeto == f"desafio:{did}" for f in filas)
    assert filas[0].detalle["titulo"] == "Auditoría: novelas"
    assert filas[1].detalle["titulo"] == "Auditoría: novelas v2"
    assert filas[4].detalle == {"titulo": "Auditoría: novelas v2"}  # el desafío ya no existe, pero queda el rastro


def test_lo_que_no_se_guarda_no_se_audita(client, db, docente):
    assert client.post(RUTA_BANCO, json={}, headers=docente.h).status_code == 422  # validación fallida
    did = client.post(RUTA_BANCO, json=payload("Para duplicar"), headers=docente.h).json()["id"]
    assert client.post(RUTA_BANCO, json=payload("para duplicar"), headers=docente.h).status_code == 422  # título repetido
    assert client.post(f"{RUTA_BANCO}/{did}/activar", headers=docente.h).status_code == 200  # ya activo: sin cambios
    assert client.delete(f"{RUTA_BANCO}/99999", headers=docente.h).status_code == 404
    assert [f.accion for f in _auditoria(db)] == ["desafio.crear"]


def test_el_administrador_tambien_deja_rastro_en_el_banco(client, db, admin):
    did = client.post(RUTA_BANCO, json=payload("Creado por admin"), headers=admin.h).json()["id"]
    f = _auditoria(db, "desafio.crear")[0]
    assert f.usuario_id == admin.id and f.objeto == f"desafio:{did}"


def test_borrar_un_desafio_auditado_no_choca_con_la_tabla_de_auditoria(client, db, docente):
    """La auditoría no tiene clave foránea a desafios: no cuenta como «historial» que impida el borrado."""
    did = client.post(RUTA_BANCO, json=payload("Efímero"), headers=docente.h).json()["id"]
    assert client.delete(f"{RUTA_BANCO}/{did}", headers=docente.h).status_code == 200


# ---------- Seed del administrador ----------
def test_seed_administrador_opcional_e_idempotente(client, db, monkeypatch):
    sembrar_administrador(db)  # vacíos: no se crea
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.rol == "administrador")) == 0
    monkeypatch.setattr(settings, "admin_email", " Jefe.Admin@Uni.edu ")
    monkeypatch.setattr(settings, "admin_password", "Admin12345!")
    sembrar_administrador(db)
    sembrar_administrador(db)
    admins = list(db.scalars(select(Usuario).where(Usuario.rol == "administrador")))
    assert len(admins) == 1 and admins[0].correo == "jefe.admin@uni.edu"
    r = login(client, "jefe.admin@uni.edu", "Admin12345!")
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "administrador"


def test_seed_administrador_sin_contrasena_no_crea_nada(client, db, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "jefe@uni.edu")
    monkeypatch.setattr(settings, "admin_password", "")
    sembrar_administrador(db)
    assert db.scalar(select(Usuario.id).where(Usuario.correo == "jefe@uni.edu")) is None


def test_seed_administrador_no_asciende_un_correo_existente(client, db, monkeypatch):
    registrar(client, correo="ana@uni.edu")
    monkeypatch.setattr(settings, "admin_email", "ana@uni.edu")
    monkeypatch.setattr(settings, "admin_password", "OtraClave123!")
    sembrar_administrador(db)
    assert db.scalar(select(Usuario.rol).where(Usuario.correo == "ana@uni.edu")) == "estudiante"
