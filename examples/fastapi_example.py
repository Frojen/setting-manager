import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import Field
from pydantic_settings import BaseSettings

from setting_manager import SettingsManager
from setting_manager.fastapi import create_settings_router
from setting_manager.storage import MemorySettingsStorage

os.environ["LOG_LEVEL"] = "INFO"
logger = logging.getLogger("root")


# --- 1. Определение настроек ---
class AppSettings(BaseSettings):
    """Пример класса с настройками для демонстрации всех возможностей."""

    # 1. Простая настройка
    app_name: str = Field(
        default="My Awesome App",
        description="Название приложения.",
        json_schema_extra={"section": "General"},
    )

    # 2. Настройка, которую не может менять никто, даже суперпользователь
    environment: str = Field(
        default="production",
        description="Среда выполнения. Изменение заблокировано.",
        json_schema_extra={"section": "System", "immutable": True},
    )

    # 3. Настройка, которую могут менять только пользователи с определенной ролью
    admin_email: str = Field(
        default="admin@example.com",
        description="Email администратора.",
        json_schema_extra={"section": "General", "required_role": "admin"},
    )

    # 4. Настройка, которую могут менять пользователи с одной из нескольких ролей
    feature_flags: list[str] = Field(
        default_factory=list,
        description="Список включенных фичей.",
        json_schema_extra={"section": "Features", "required_role": ["developer", "tester"]},
    )

    # 5. Чувствительная настройка
    api_key: str = Field(
        default="default_secret_key",
        description="Секретный ключ для API.",
        json_schema_extra={"section": "Security", "sensitive": True},
    )

    # 6. Настройка, изменение которой запрещено для обычных пользователей, но разрешено для суперпользователя
    service_host: str = Field(
        default="localhost",
        description="Хост внутреннего сервиса.",
        json_schema_extra={"section": "System", "allow_change": False},
    )

    LOG_LEVEL: str = Field(
        default="INFO",
        json_schema_extra=dict(
            section="Feature",
        ),
        description="Уровень логирования",
    )


# Создаем экземпляр настроек
app_settings = AppSettings()

# Создаем хранилище
storage = MemorySettingsStorage()

# Создаем менеджер настроек
settings_manager = SettingsManager(
    settings_instance=app_settings,
    storage=storage,
)


# --- 2. Зависимость для определения роли пользователя ---
# Зависимость для проверки доступа
# В реальном приложении здесь была бы логика проверки токена, сессии и т.д.
async def require_admin_access(request: Request) -> str:
    """
    Пример зависимости для проверки прав доступа.
    В реальном приложении здесь может быть проверка JWT токена, ролей пользователя и т.д.
    """
    # Здесь можно добавить любую логику проверки доступа
    # Например, проверка JWT токена, ролей пользователя и т.д.

    # В этом примере просто проверяем наличие заголовка X-Admin-Access
    # В реальном приложении используйте вашу систему аутентификации

    user_role = request.headers.get("X-User-Role", "admin")

    # Проверяем валидность роли (опционально)
    valid_roles = ["user", "admin"]
    if user_role not in valid_roles:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    return user_role


# --- 4. Создание приложения FastAPI ---
app = FastAPI(
    title="Settings Manager Example",
    version="1.2.3",
)

# Создаем и подключаем роутер для управления настройками
settings_router = create_settings_router(
    settings_manager=settings_manager,
    router_prefix="/settings",
    security_dependency=require_admin_access,
    superuser_role="admin",
    app=app,  # Передаем экземпляр FastAPI
)
app.include_router(settings_router)


@settings_manager.on_change("LOG_LEVEL")
def on_log_level_change(old_value: str, new_value: str):
    # Обновляем конфигурацию логгера
    logger.setLevel(new_value)
    logger.debug("Debug message")
    logger.info("Info message")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup

    # Инициализируем менеджер
    await settings_manager.initialize()

    yield
    # Shutdown
    pass


@app.get("/")
async def root():
    """Главная страница с примерами использования."""
    return {
        "message": "Welcome to the Settings Manager example!",
        "current_app_name": settings_manager.get_setting("app_name"),
        "docs": "Перейдите на /docs для просмотра API.",
        "settings_ui": "Перейдите на /settings для управления настройками.",
        "tip": "Используйте Postman или curl для отправки запросов с заголовком X-User-Role.",
        "example_curl": "curl -X GET http://127.0.0.1:8000/settings -H 'X-User-Role: superuser'",
    }


# --- 5. Запуск приложения ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
