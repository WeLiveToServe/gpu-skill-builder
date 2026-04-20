from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

LOCAL_ENV_FILE = Path(__file__).parent / ".env"
SHARED_ENV_FILE = Path.home() / "dev" / ".env"


def _seed_environment() -> None:
    """
    Load shared then local .env values into process env.
    Precedence:
      1) Existing process env (highest)
      2) Repo-local .env
      3) Shared /dev/.env (fallback)
    """
    original_keys = set(os.environ.keys())

    if SHARED_ENV_FILE.exists():
        for key, value in dotenv_values(SHARED_ENV_FILE).items():
            if key and value is not None and key not in os.environ:
                os.environ[key] = value

    if LOCAL_ENV_FILE.exists():
        for key, value in dotenv_values(LOCAL_ENV_FILE).items():
            if not key or value is None:
                continue
            if key in original_keys:
                continue
            os.environ[key] = value


_seed_environment()


class Settings(BaseSettings):
    # Provider credentials — optional at settings layer; each provider validates as needed.
    hf_token: str = Field(default="", alias="HF_TOKEN")
    digitalocean_token: str = Field(default="", alias="DIGITALOCEAN_ACCESS_TOKEN")
    modal_token_id: str = Field(default="", alias="MODAL_TOKEN_ID")
    modal_token_secret: str = Field(default="", alias="MODAL_TOKEN_SECRET")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # OpenAI-compatible OpenRouter endpoint config (provider-specific names prevent OPENAI_API_KEY collisions).
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openrouter_model: str = Field(default="qwen/qwen3.6-plus", alias="OPENROUTER_MODEL")

    # Programmatic deployment controls — never delegated to the LLM.
    max_deployment_hours: int = 8
    uptime_report_interval_minutes: int = 30

    # Operational guardrails.
    max_spend_per_instance_usd: float = 5.0
    max_concurrent_instances: int = 2
    stuck_pending_minutes: int = 15
    watchdog_check_interval_minutes: int = 5

    # Fleet monitoring / alerting
    monitor_enabled: bool = Field(default=False, alias="GPU_MONITOR_ENABLED")
    monitor_interval_minutes: int = Field(default=5, alias="GPU_MONITOR_INTERVAL_MINUTES")
    monitor_runtime_alert_minutes: int = Field(default=120, alias="GPU_MONITOR_RUNTIME_ALERT_MINUTES")
    monitor_auto_stop_minutes: int = Field(default=0, alias="GPU_MONITOR_AUTO_STOP_MINUTES")

    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
