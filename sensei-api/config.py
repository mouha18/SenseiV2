from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase — restricted (non-superuser) role DSN, RLS-enforced via SET LOCAL (ADR-0009).
    # Never the service-role key.
    SUPABASE_DB_DSN: str
    SUPABASE_URL: str
    SUPABASE_STORAGE_KEY: str

    GEMINI_API_KEY: str
    KEY_ENCRYPTION_SECRET: str

    CONVEX_URL: str
    CONVEX_SITE_URL: str
    CONVEX_SERVICE_SECRET: str

    ALLOWED_ORIGINS: str

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = []
        for origin in self.ALLOWED_ORIGINS.split(","):
            origin = origin.strip()
            if not origin:
                continue
            if not origin.startswith("http://") and not origin.startswith("https://"):
                origin = f"https://{origin}"
            origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
