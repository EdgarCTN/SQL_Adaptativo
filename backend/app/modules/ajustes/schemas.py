from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.desafios.schemas import AjusteNivelOut, ConceptoOut

AccionRespuesta = Literal["aceptar", "mantener"]


class ResponderIn(BaseModel):
    accion: AccionRespuesta


class AjustePendienteOut(BaseModel):
    id: int
    concepto: ConceptoOut
    modo: Literal["aviso_previo", "preguntar"]
    texto: str  # mensaje fijo (retiro_aviso_previo o retiro_preguntar) con el concepto ya reemplazado
    creado_en: datetime


class ListaAjustesOut(BaseModel):
    ajustes: list[AjustePendienteOut]


class ResponderOut(BaseModel):
    estado: Literal["aplicado", "mantenido", "caducado"]
    mensaje: str
    ajuste_nivel: AjusteNivelOut | None = None  # solo si se aplicó el retiro
