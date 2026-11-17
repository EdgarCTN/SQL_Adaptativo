from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario
from app.modules.progreso.fechas import interpretar_rango
from app.modules.reportes import service
from app.modules.reportes.schemas import ReporteOut

# Todo el router exige docente o administrador (el estudiante recibe 403). Misma dependencia que el banco de desafíos.
docente_o_administrador = requiere_rol(Rol.docente, Rol.administrador)

router = APIRouter(prefix="/reportes", tags=["Reportes"], dependencies=[Depends(docente_o_administrador)])

_DESDE = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO")
_HASTA = Query(default=None, max_length=40, description="AAAA-MM-DD o fecha y hora ISO")


@router.get("", response_model=ReporteOut)
def reporte(desde: str | None = _DESDE, hasta: str | None = _HASTA, db: Session = Depends(get_db)):
    """Reporte agregado y seudonimizado del periodo; los grupos pequeños salen como «suprimido»."""
    d, h = interpretar_rango(desde, hasta)
    return service.reporte(db, d, h)


@router.get("/exportar")
def exportar(
    tipo: str = Query(default="intentos", max_length=20, description="intentos, ayudas, cambios_ns, indicadores o todos (ZIP)"),
    desde: str | None = _DESDE,
    hasta: str | None = _HASTA,
    usuario: Usuario = Depends(docente_o_administrador),
    db: Session = Depends(get_db),
):
    """CSV seudonimizado (nunca nombres ni correos). `tipo=todos` devuelve un ZIP con los cuatro CSV."""
    d, h = interpretar_rango(desde, hasta)
    contenido, mime, nombre = service.exportar(db, usuario.id, tipo, d, h)
    return Response(
        content=contenido,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"},
    )
