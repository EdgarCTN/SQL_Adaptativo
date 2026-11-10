from datetime import datetime

from pydantic import BaseModel


class NotificacionOut(BaseModel):
    id: int
    tipo: str
    texto: str
    regla: str | None
    concepto_id: int | None
    leida: bool
    creada_en: datetime
    ajuste_id: int | None


class ListaNotificacionesOut(BaseModel):
    notificaciones: list[NotificacionOut]
    no_leidas: int


class LeidaOut(BaseModel):
    ok: bool
    id: int


class LeerTodasOut(BaseModel):
    ok: bool
    actualizadas: int
