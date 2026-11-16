"""Environment settings (secrets and deployment-specific values) via pydantic-settings.

Every secret is a SecretStr so it is masked in repr/logs. Variable names are listed in
.env.example; never add a default value for a real secret.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    config_dir: Path = Field(default=REPO_ROOT / "config", alias="OSINT_CONFIG_DIR")
    demo_mode: bool = Field(default=False, alias="OSINT_DEMO_MODE")

    # Contains credentials => SecretStr, no default. Required from Phase 2 on.
    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: SecretStr | None = Field(default=None, alias="NEO4J_PASSWORD")

    secret_key: SecretStr | None = Field(default=None, alias="OSINT_SECRET_KEY")
    encryption_key: SecretStr | None = Field(default=None, alias="OSINT_ENCRYPTION_KEY")


@lru_cache(maxsize=1)
def get_env_settings() -> EnvSettings:
    return EnvSettings()
