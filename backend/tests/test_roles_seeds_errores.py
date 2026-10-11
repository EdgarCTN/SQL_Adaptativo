from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errores import registrar_manejadores
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Concepto
from app.seeds.seed import sembrar_todo
from conftest import API, cabecera, login, registrar, token_de

CODIGOS = [
    "filtrado", "ordenamiento", "conteo_agregacion", "join", "group_by",
    "having", "left_join", "subconsulta", "join_agregacion", "funciones_ventana",
]


def _mini_app() -> FastAPI:
    mini = FastAPI()
    registrar_manejadores(mini)

    @mini.get("/solo-docentes", dependencies=[Depends(requiere_rol(Rol.docente))])
    def solo_docentes():
        return {"ok": True}

    @mini.get("/solo-estudiantes", dependencies=[Depends(requiere_rol(Rol.estudiante))])
    def solo_estudiantes():
        return {"ok": True}

    @mini.get("/falla")
    def falla():
        raise RuntimeError("detalle interno secreto")

    return mini


def test_rol_indebido_403_y_rol_correcto_200(client):
    registrar(client)
    token = token_de(client)
    mini = TestClient(_mini_app())
    r = mini.get("/solo-docentes", headers=cabecera(token))
    assert r.status_code == 403
    assert r.json()["error"] is True and "permiso" in r.json()["mensaje"]
    assert mini.get("/solo-estudiantes", headers=cabecera(token)).status_code == 200
    assert mini.get("/solo-docentes").status_code == 401


def test_error_inesperado_no_filtra_detalles():
    r = TestClient(_mini_app(), raise_server_exceptions=False).get("/falla")
    assert r.status_code == 500
    assert r.json()["error"] is True
    assert "secreto" not in r.text and "Traceback" not in r.text


def test_seeds_idempotentes(client, db):
    sembrar_todo(db)
    sembrar_todo(db)
    codigos = list(db.scalars(select(Concepto.codigo).order_by(Concepto.id)))
    assert codigos == CODIGOS
    assert db.scalar(select(func.count()).select_from(Concepto)) == 10
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.correo == "estudiante@demo.edu")) == 1
    assert all(c.prerrequisito_id is None for c in db.scalars(select(Concepto)))


def test_usuario_demo_puede_entrar(client):
    r = login(client, "estudiante@demo.edu", "Demo12345!")
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "estudiante"
