"""Seeds idempotentes. Las entregas siguientes añaden sus funciones a sembrar_todo()."""
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import hashear_password
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Concepto
from app.modules.desafios.seeds import sembrar_desafios
from app.modules.linea_base.models import LineaBaseCuestionario

log = logging.getLogger("app.seeds")
RUTA_CUESTIONARIO = Path(__file__).resolve().parent / "cuestionario_linea_base.json"

CONCEPTOS = [
    ("filtrado", "Filtrado (WHERE)"),
    ("ordenamiento", "Ordenamiento (ORDER BY)"),
    ("conteo_agregacion", "Conteo y agregación"),
    ("join", "JOIN"),
    ("group_by", "GROUP BY"),
    ("having", "HAVING"),
    ("left_join", "LEFT JOIN"),
    ("subconsulta", "Subconsultas"),
    ("join_agregacion", "JOIN con agregación"),
    ("funciones_ventana", "Funciones de ventana"),
]


def sembrar_conceptos(db: Session) -> None:
    existentes = set(db.scalars(select(Concepto.codigo)))
    for codigo, nombre in CONCEPTOS:
        if codigo not in existentes:
            db.add(Concepto(codigo=codigo, nombre=nombre, prerrequisito_id=None))
    db.commit()


def sembrar_cuestionario(db: Session) -> None:
    """Carga seeds/cuestionario_linea_base.json (sin modificarlo) como versión activa."""
    try:
        datos = json.loads(RUTA_CUESTIONARIO.read_text(encoding="utf-8-sig"))
        version = int(datos["version"])
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("No se pudo leer %s; el cuestionario quedará no disponible.", RUTA_CUESTIONARIO)
        return
    if db.scalar(select(LineaBaseCuestionario.id).where(LineaBaseCuestionario.version == version)):
        return
    db.add(LineaBaseCuestionario(version=version, activo=True, contenido=datos))
    db.commit()


def sembrar_usuario_demo(db: Session) -> None:
    if not settings.seed_usuario_demo:
        return
    correo = settings.demo_email.strip().lower()
    if db.scalar(select(Usuario.id).where(Usuario.correo == correo)):
        return
    db.add(
        Usuario(
            nombre="Estudiante Demo",
            correo=correo,
            hash_password=hashear_password(settings.demo_password),
            rol=Rol.estudiante.value,
        )
    )
    db.commit()


def sembrar_todo(db: Session) -> None:
    sembrar_conceptos(db)
    sembrar_desafios(db)
    sembrar_cuestionario(db)
    sembrar_usuario_demo(db)
