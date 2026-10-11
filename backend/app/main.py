from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import health
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errores import registrar_manejadores
from app.modules.auth.router import perfil_router
from app.modules.auth.router import router as auth_router
from app.modules.linea_base.router import router as linea_base_router
from app.seeds.seed import sembrar_todo


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create_all (sin Alembic)
    with SessionLocal() as db:
        sembrar_todo(db)
    yield


app = FastAPI(title=settings.app_nombre, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_lista,
    allow_methods=["*"],
    allow_headers=["*"],
)
registrar_manejadores(app)

api = APIRouter(prefix=settings.api_prefix)
api.include_router(health.router)
api.include_router(auth_router)
api.include_router(perfil_router)
api.include_router(linea_base_router)
app.include_router(api)
