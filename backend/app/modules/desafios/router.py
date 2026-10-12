from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios import service
from app.modules.desafios.schemas import (
    AbandonarOut,
    DesafioDetalleOut,
    IniciarOut,
    IntentoIn,
    IntentoOut,
    ListaDesafiosOut,
)

router = APIRouter(prefix="/desafios", tags=["Desafíos"])
_estudiante = requiere_rol(Rol.estudiante)


@router.get("", response_model=ListaDesafiosOut)
def listar(
    concepto: str | None = Query(default=None, max_length=50, description="Código del concepto"),
    usuario: Usuario = Depends(_estudiante),
    db: Session = Depends(get_db),
):
    return service.listar(db, usuario, concepto)


@router.get("/{desafio_id}", response_model=DesafioDetalleOut)
def ver(desafio_id: int, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.detalle(db, usuario, desafio_id)


@router.post("/{desafio_id}/iniciar", response_model=IniciarOut)
def iniciar(desafio_id: int, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.iniciar(db, usuario, desafio_id)


@router.post("/{desafio_id}/intentos", response_model=IntentoOut)
def intento(
    desafio_id: int, datos: IntentoIn, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)
):
    return service.registrar_intento(db, usuario, desafio_id, datos.codigo)


@router.post("/{desafio_id}/abandonar", response_model=AbandonarOut)
def abandonar(desafio_id: int, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.abandonar(db, usuario, desafio_id)
