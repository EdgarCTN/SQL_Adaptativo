"""Configuración central: variables de entorno y .env de la raíz del proyecto."""
import secrets
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]
DB_POR_DEFECTO = f"sqlite:///{(RAIZ / 'backend' / 'desafios_sql.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore"
    )

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

    @field_validator("database_url")
    @classmethod
    def _normalizar_db(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return DB_POR_DEFECTO
        prefijo = "sqlite:///"
        if v.startswith(prefijo) and not v.startswith(prefijo + "/"):
            resto = v[len(prefijo):]
            if resto and not resto.startswith(":memory:") and not Path(resto).is_absolute():
                return f"{prefijo}{(RAIZ / resto).as_posix()}"
        return v

    @field_validator("secret_key")
    @classmethod
    def _clave(cls, v: str) -> str:
        return v.strip() or secrets.token_urlsafe(48)

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
