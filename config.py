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

    # Operational guardrails
    max_spend_per_instance_usd: float = 5.0      # pre-flight: hours × rate must be under this
    max_concurrent_instances: int = 2            # hard cap on live instances across all providers
    stuck_pending_minutes: int = 15              # watchdog: destroy if pending longer than this
    watchdog_check_interval_minutes: int = 5     # how often the watchdog polls

    model_config = SettingsConfigDict(
        env_file="C:/Users/keith/dev/.env",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
