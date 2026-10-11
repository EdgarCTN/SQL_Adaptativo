from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import ahora_utc, engine

router = APIRouter(tags=["Sistema"])


@router.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        bd = "ok"
    except Exception:
        bd = "no_disponible"
    return {"estado": "ok", "base_datos": bd, "fecha": ahora_utc().isoformat()}
