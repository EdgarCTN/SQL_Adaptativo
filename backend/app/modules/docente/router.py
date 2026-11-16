from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol
from app.modules.docente import service
from app.modules.docente.schemas import (
    DesafioDocenteOut,
    DesafioIn,
    ListaDocenteOut,
    MensajeDocenteOut,
    OpcionesOut,
    ValidacionOut,
)

# Todo el router exige docente o administrador: el estudiante recibe 403 con un mensaje claro.
router = APIRouter(
    prefix="/docente/desafios",
    tags=["Docente"],
    dependencies=[Depends(requiere_rol(Rol.docente, Rol.administrador))],
)


@router.get("/opciones", response_model=OpcionesOut)
def opciones(db: Session = Depends(get_db)):
    return service.opciones(db)


@router.post("/validar", response_model=ValidacionOut)
def validar(datos: DesafioIn, desafio_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    """Valida un borrador sin guardarlo (sandbox incluido). `desafio_id` evita marcar el propio título como repetido."""
    return service.validar(db, datos, desafio_id)


@router.get("", response_model=ListaDocenteOut)
def listar(
    concepto: str | None = Query(default=None, max_length=50),
    dificultad: str | None = Query(default=None, max_length=2),
    estado: str | None = Query(default=None, pattern="^(activos|inactivos|todos)$"),
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    return service.listar(db, concepto, dificultad, estado, q)


@router.post("", response_model=DesafioDocenteOut, status_code=201)
def crear(datos: DesafioIn, db: Session = Depends(get_db)):
    return service.crear(db, datos)


@router.get("/{desafio_id}", response_model=DesafioDocenteOut)
def ver(desafio_id: int, db: Session = Depends(get_db)):
    return service.detalle(db, desafio_id)


@router.put("/{desafio_id}", response_model=DesafioDocenteOut)
def actualizar(desafio_id: int, datos: DesafioIn, db: Session = Depends(get_db)):
    return service.actualizar(db, desafio_id, datos)


@router.post("/{desafio_id}/activar", response_model=MensajeDocenteOut)
def activar(desafio_id: int, db: Session = Depends(get_db)):
    return service.cambiar_activo(db, desafio_id, True)


@router.post("/{desafio_id}/desactivar", response_model=MensajeDocenteOut)
def desactivar(desafio_id: int, db: Session = Depends(get_db)):
    return service.cambiar_activo(db, desafio_id, False)


@router.delete("/{desafio_id}", response_model=MensajeDocenteOut)
def eliminar(desafio_id: int, db: Session = Depends(get_db)):
    return service.eliminar(db, desafio_id)
