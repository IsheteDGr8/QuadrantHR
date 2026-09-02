from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "QuadrantHR"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5170,http://127.0.0.1:5170"

    # PostgreSQL stands in for Azure SQL locally
    database_url: str = "postgresql+psycopg://quadranthr:quadranthr@localhost:5432/quadranthr"

    # JWT local auth (Entra later)
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # Azurite / Azure Blob
    azure_storage_connection_string: str = (
        "DefaultEndpointsProtocol=http;"
        "AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    azure_blob_container: str = "hr-documents"

    # Redis (Celery / cache)
    redis_url: str = "redis://localhost:6379/0"

    # LLM: mock | ollama | azure_openai
    llm_provider: str = "mock"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
