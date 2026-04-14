from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Provider credentials
    hf_token: str = Field(alias="HF_TOKEN")
    digitalocean_token: str = Field(default="", alias="DIGITALOCEAN_TOKEN")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # Programmatic deployment controls — never delegated to the LLM
    max_deployment_hours: int = 8
    uptime_report_interval_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file="C:/Users/keith/dev/.env",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
