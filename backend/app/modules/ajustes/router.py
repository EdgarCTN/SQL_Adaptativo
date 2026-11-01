from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.ajustes import service
from app.modules.ajustes.schemas import ListaAjustesOut, ResponderIn, ResponderOut
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario

router = APIRouter(prefix="/ajustes", tags=["Ajustes de ayuda"])
_estudiante = requiere_rol(Rol.estudiante)


@router.get("/pendientes", response_model=ListaAjustesOut)
def pendientes(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.listar_pendientes(db, usuario)


@router.post("/{ajuste_id}/responder", response_model=ResponderOut)
def responder(ajuste_id: int, datos: ResponderIn, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.responder(db, usuario, ajuste_id, datos.accion)
