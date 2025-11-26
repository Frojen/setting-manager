import pytest
from pydantic import Field
from pydantic_settings import BaseSettings

from setting_manager import SettingsManager
from setting_manager.storage import MemorySettingsStorage

# --- 1. Общие классы и константы для тестов ---


class AppSettings(BaseSettings):
    """Настройки для тестов."""

    app_name: str = Field(default="My App", json_schema_extra={"section": "General"})
    environment: str = Field(default="prod", json_schema_extra={"section": "System", "immutable": True})
    admin_email: str = Field(
        default="admin@test.com", json_schema_extra={"section": "General", "required_role": "admin"}
    )
    feature_flags: list[str] = Field(
        default_factory=list, json_schema_extra={"section": "Features", "required_role": ["developer", "tester"]}
    )
    api_key: str = Field(default="secret", json_schema_extra={"section": "Security", "sensitive": True})
    service_host: str = Field(default="localhost", json_schema_extra={"section": "System", "allow_change": False})


# Константы ролей, доступные для всех тестов
SUPERUSER_ROLE = "superuser"
ADMIN_ROLE = "admin"
DEVELOPER_ROLE = "developer"
REGULAR_USER_ROLE = "user"
TESTER_ROLE = "tester"


# --- 2. Фикстура для pytest ---


@pytest.fixture
async def manager() -> SettingsManager:
    """Создает и инициализирует SettingsManager для каждого теста."""
    settings = AppSettings()
    storage = MemorySettingsStorage()
    manager = SettingsManager(
        settings_instance=settings,
        storage=storage,
        superuser_role=SUPERUSER_ROLE,
    )
    await manager.initialize()
    return manager
