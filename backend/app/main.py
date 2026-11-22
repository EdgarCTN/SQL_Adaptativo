from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import health
from app.core.config import settings
from app.core.db import SessionLocal, cargar_modelos, init_db, verificar_esquema
from app.core.errores import registrar_manejadores
from app.modules.admin.router import router as admin_router
from app.modules.ajustes.router import router as ajustes_router
from app.modules.asistencia.router import router as asistencia_router
from app.modules.auth.router import perfil_router
from app.modules.auth.router import router as auth_router
from app.modules.desafios.router import router as desafios_router
from app.modules.docente.router import router as docente_router
from app.modules.linea_base.router import router as linea_base_router
from app.modules.notificaciones.router import router as notificaciones_router
from app.modules.progreso.router import router as progreso_router
from app.modules.reportes.router import router as reportes_router
from app.seeds.seed import sembrar_todo


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.crear_tablas:
        init_db()  # desarrollo y pruebas: create_all
    else:
        cargar_modelos()
        verificar_esquema()  # producción: el esquema lo crea 'alembic upgrade head' (build de Render)
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
api.include_router(desafios_router)
api.include_router(asistencia_router)
api.include_router(progreso_router)
api.include_router(ajustes_router)
api.include_router(notificaciones_router)
api.include_router(docente_router)
api.include_router(admin_router)
api.include_router(reportes_router)
app.include_router(api)
