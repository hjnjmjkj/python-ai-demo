from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dashscope_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.7-plus"
    qwen_embedding_model: str = "text-embedding-v4"
    qwen_embedding_dimensions: int = 1024
    mcp_server_url: str = "http://localhost:8081"
    pgvector_host: str = "localhost"
    pgvector_port: int = 5556
    postgres_db: str = "pgvector"
    postgres_user: str = "pgvector"
    postgres_password: str = "pgvector"
    vector_table: str = "python_vector_store"
    max_document_chars: int = 20_000
    max_history_messages: int = 20

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.pgvector_host}:{self.pgvector_port}/{self.postgres_db}"
        )


settings = Settings()
