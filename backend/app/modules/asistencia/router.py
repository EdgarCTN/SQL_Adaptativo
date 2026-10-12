from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.asistencia import service
from app.modules.asistencia.llm.base import LLMProvider
from app.modules.asistencia.llm.fabrica import obtener_proveedor
from app.modules.asistencia.schemas import AyudaIn, AyudaOut, ValoracionIn, ValoracionOut
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario

router = APIRouter(tags=["Ayuda"])
_estudiante = requiere_rol(Rol.estudiante)


def get_proveedor() -> LLMProvider:
    return obtener_proveedor()


@router.post("/desafios/{desafio_id}/ayuda", response_model=AyudaOut)
def pedir_ayuda(
    desafio_id: int,
    datos: AyudaIn | None = None,
    usuario: Usuario = Depends(_estudiante),
    db: Session = Depends(get_db),
    proveedor: LLMProvider = Depends(get_proveedor),
):
    return service.solicitar_ayuda(db, usuario, desafio_id, datos.mensaje_estudiante if datos else None, proveedor)


@router.post("/ayudas/{solicitud_id}/valoracion", response_model=ValoracionOut)
def valorar(
    solicitud_id: int, datos: ValoracionIn, usuario: Usuario = Depends(_estudiante), db: Session = Depends(get_db)
):
    return service.valorar(db, usuario, solicitud_id, datos.valor)
