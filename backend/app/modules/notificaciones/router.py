from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.notificaciones import service
from app.modules.notificaciones.schemas import LeidaOut, LeerTodasOut, ListaNotificacionesOut

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])
_estudiante = requiere_rol(Rol.estudiante)


@router.get("", response_model=ListaNotificacionesOut)
def listar(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.listar(db, usuario)


@router.post("/{notificacion_id}/leida", response_model=LeidaOut)
def marcar_leida(notificacion_id: int, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.marcar_leida(db, usuario, notificacion_id)


@router.post("/leer-todas", response_model=LeerTodasOut)
def marcar_todas(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.marcar_todas(db, usuario)
