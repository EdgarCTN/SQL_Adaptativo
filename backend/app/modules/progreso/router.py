from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.progreso import service
from app.modules.progreso.fechas import interpretar_rango
from app.modules.progreso.schemas import EvolucionOut, ListaIntentosOut, ResumenProgresoOut

router = APIRouter(prefix="/progreso", tags=["Progreso"])
_estudiante = requiere_rol(Rol.estudiante)


@router.get("/resumen", response_model=ResumenProgresoOut)
def resumen(usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)):
    return service.resumen(db, usuario)


@router.get("/intentos", response_model=ListaIntentosOut)
def intentos(
    desafio_id: int | None = Query(default=None, ge=1),
    desde: str | None = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO"),
    hasta: str | None = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO"),
    pagina: int = Query(default=1, ge=1),
    tam: int = Query(default=20, ge=1, le=service.TAM_MAXIMO),
    usuario: Usuario = Depends(_estudiante),
    db: Session = Depends(get_db),
):
    d, h = interpretar_rango(desde, hasta)
    return service.intentos(db, usuario, desafio_id, d, h, pagina, tam)


@router.get("/evolucion", response_model=EvolucionOut)
def evolucion(
    concepto: str | None = Query(default=None, max_length=50, description="Código del concepto"),
    desde: str | None = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO"),
    hasta: str | None = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO"),
    usuario: Usuario = Depends(_estudiante),
    db: Session = Depends(get_db),
):
    d, h = interpretar_rango(desde, hasta)
    return service.evolucion(db, usuario, concepto, d, h)
