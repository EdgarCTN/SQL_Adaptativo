from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.progreso import service
from app.modules.progreso.schemas import ResumenProgresoOut

router = APIRouter(prefix="/progreso", tags=["Progreso"])


@router.get("/resumen", response_model=ResumenProgresoOut)
def resumen(usuario: Usuario = Depends(requiere_rol(Rol.estudiante)), db: Session = Depends(get_db)):
    return service.resumen(db, usuario)
