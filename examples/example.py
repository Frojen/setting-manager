import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import Field
from pydantic_settings import BaseSettings

from setting_manager import SettingsManager
from setting_manager.fastapi.route import create_settings_router
from setting_manager.storage import MemorySettingsStorage

os.environ["LOG_LEVEL"] = "INFO"


class AppSettings(BaseSettings):
    """Настройки приложения"""

    LOG_LEVEL: str = Field(
        default="INFO",
        json_schema_extra=dict(
            section="Feature",
        ),
        description="Уровень логирования",
    )

    ADMIN_API_KEY: str = Field(
        default="default-key",
        json_schema_extra=dict(
            section="Security",
            allow_change=True,
            sensitive=True,
            required_role="admin",  # Только админы могут изменять
        ),
        description="API ключ для административных функций",
    )

    DATABASE_URL: str = Field(
        default="mongodb://localhost:27017",
        json_schema_extra=dict(
            required_role="admin",  # Только админы могут изменять
        ),
        description="URL подключения к MongoDB",
    )

    DEBUG: bool = Field(default=False, description="Режим отладки")

    SECRET_WORKERS: int = Field(default=4, description="Максимальное количество worker процессов")

    ENCRYPTION_SALT: str = Field(
        default="default-salt",
        json_schema_extra=dict(
            sensitive=True,
            allow_change=False,
            section="Security",
        ),
        description="Соль для шифрования данных",
    )


# Создаем экземпляр настроек
app_settings = AppSettings()

# Создаем хранилище
storage = MemorySettingsStorage()

# Создаем менеджер настроек
settings_manager = SettingsManager(settings_instance=app_settings, storage=storage)


# Зависимость для проверки доступа
async def require_admin_access(request: Request) -> str:
    """
    Пример зависимости для проверки прав доступа.
    В реальном приложении здесь может быть проверка JWT токена, ролей пользователя и т.д.
    """
    # Здесь можно добавить любую логику проверки доступа
    # Например, проверка JWT токена, ролей пользователя и т.д.

    # В этом примере просто проверяем наличие заголовка X-Admin-Access
    # В реальном приложении используйте вашу систему аутентификации

    return "user"

    user_role = request.headers.get("X-User-Role", "user")

    # Проверяем валидность роли (опционально)
    valid_roles = ["user", "admin"]
    if user_role not in valid_roles:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    return user_role


@settings_manager.on_change("LOG_LEVEL")
def on_log_level_change(old_value: str, new_value: str):
    # Обновляем конфигурацию логгера
    logging.getLogger().setLevel(new_value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup

    # Инициализируем менеджер
    await settings_manager.initialize()

    yield
    # Shutdown
    pass


app = FastAPI(lifespan=lifespan)

# Добавляем роуты для настроек
settings_router = create_settings_router(settings_manager, security_dependency=require_admin_access)
app.include_router(settings_router)


@app.get("/")
async def root():
    return {"message": "Settings Management API"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
