from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.linea_base import service
from app.modules.linea_base.schemas import (
    ConsentimientoIn,
    ConsentimientoOut,
    CuestionarioOut,
    EstadoOut,
    RespuestasIn,
    RespuestasOut,
)

router = APIRouter(prefix="/linea-base", tags=["Línea base"])
_estudiante = requiere_rol(Rol.estudiante)


@router.get("/estado", response_model=EstadoOut)
def ver_estado(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.estado(db, usuario)


@router.post("/consentimiento", response_model=ConsentimientoOut)
def consentimiento(
    datos: ConsentimientoIn, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)
):
    return service.registrar_consentimiento(db, usuario, datos.acepta)


@router.get("/cuestionario", response_model=CuestionarioOut)
def cuestionario(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.obtener_cuestionario(db, usuario)


@router.post("/respuestas", response_model=RespuestasOut)
def respuestas(datos: RespuestasIn, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.guardar_respuestas(db, usuario, datos)
