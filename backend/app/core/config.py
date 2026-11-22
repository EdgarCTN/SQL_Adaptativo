"""Configuración central: variables de entorno y .env de la raíz del proyecto."""
import secrets
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]
DB_POR_DEFECTO = f"sqlite:///{(RAIZ / 'backend' / 'desafios_sql.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # "desarrollo" (por defecto) o "produccion". En producción la app se niega a arrancar sin
    # SECRET_KEY y ANON_SALT, o con una base SQLite (ver _validar_produccion).
    entorno: str = "desarrollo"
    app_nombre: str = "Desafíos SQL adaptativos"
    api_prefix: str = "/api/v1"
    database_url: str = DB_POR_DEFECTO
    secret_key: str = ""
    access_token_expire_minutes: int = Field(default=60, gt=0)
    cors_origins: str = "http://localhost:5173"
    dominio_institucional: str = ""
    seed_usuario_demo: bool = True
    demo_email: str = "estudiante@demo.edu"
    demo_password: str = "Demo12345!"
    docente_email: str = ""  # vacío (junto con la contraseña) = no se crea el docente de pruebas
    docente_password: str = ""
    admin_email: str = ""  # vacío (junto con la contraseña) = no se crea el administrador inicial
    admin_password: str = ""
    sandbox_tiempo_max_seg: float = Field(default=2.0, gt=0)
    sandbox_max_filas: int = Field(default=200, gt=0)
    llm_provider: str = "mock"
    llm_model: str = "claude-haiku-5-5"
    anthropic_api_key: str = ""
    groq_api_key: str = ""  # también se lee de la variable de entorno GROQ_API_KEY
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-6-luna"
    anon_salt: str = ""  # sal del HMAC de los seudónimos; vacía = sal temporal (no estable entre reinicios)
    # Pool de conexiones (solo PostgreSQL; SQLite no lo usa). Valores pequeños: Render free (512 MB) y Neon free.
    db_pool_size: int = Field(default=5, gt=0)
    db_max_overflow: int = Field(default=5, ge=0)
    db_pool_recycle: int = Field(default=280, gt=0)  # seg.; < 300 porque Neon suspende el cómputo ocioso a los 5 min

    @field_validator("entorno")
    @classmethod
    def _normalizar_entorno(cls, v: str) -> str:
        v = (v or "").strip().lower() or "desarrollo"
        alias = {"production": "produccion", "prod": "produccion", "development": "desarrollo", "dev": "desarrollo"}
        v = alias.get(v, v)
        if v not in ("desarrollo", "produccion"):
            raise ValueError("ENTORNO debe ser 'desarrollo' o 'produccion'")
        return v

    @field_validator("database_url")
    @classmethod
    def _normalizar_db(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return DB_POR_DEFECTO
        # Neon/Heroku entregan postgres:// o postgresql://; SQLAlchemy usaría psycopg2 (no instalado): forzar psycopg 3.
        for viejo in ("postgresql://", "postgres://"):
            if v.startswith(viejo):
                return "postgresql+psycopg://" + v[len(viejo):]
        prefijo = "sqlite:///"
        if v.startswith(prefijo) and not v.startswith(prefijo + "/"):
            resto = v[len(prefijo):]
            if resto and not resto.startswith(":memory:") and not Path(resto).is_absolute():
                return f"{prefijo}{(RAIZ / resto).as_posix()}"
        return v

    @field_validator("secret_key", "anon_salt")
    @classmethod
    def _recortar(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _validar_entorno(self) -> "Settings":
        if self.entorno == "produccion":
            faltan = [n for n, v in (("SECRET_KEY", self.secret_key), ("ANON_SALT", self.anon_salt)) if not v]
            if faltan:
                raise ValueError(f"ENTORNO=produccion: faltan {', '.join(faltan)} (no se generan claves temporales)")
            if len(self.secret_key) < 32:
                raise ValueError("ENTORNO=produccion: SECRET_KEY debe tener al menos 32 caracteres")
            if self.database_url.startswith("sqlite"):
                raise ValueError("ENTORNO=produccion: DATABASE_URL no puede ser SQLite; usa PostgreSQL (Neon)")
        elif not self.secret_key:
            # Desarrollo: clave temporal (las sesiones se pierden al reiniciar), como antes.
            self.secret_key = secrets.token_urlsafe(48)
        return self

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def dominios_permitidos(self) -> list[str]:
        return [
            d.strip().lower().lstrip("@")
            for d in self.dominio_institucional.split(",")
            if d.strip()
        ]


settings = Settings()
