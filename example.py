import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings

from setting_manager.fastapi.route import create_settings_router
from setting_manager.manager import SettingsManager
from setting_manager.storage import MemorySettingsStorage

os.environ["LOG_LEVEL"] = "INFO"


class AppSettings(BaseSettings):
    """Настройки приложения"""

    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    DATABASE_URL: str = Field(default="mongodb://localhost:27017", description="URL подключения к MongoDB")

    DEBUG: bool = Field(default=False, description="Режим отладки")

    MAX_WORKERS: int = Field(default=4, description="Максимальное количество worker процессов")


# Создаем экземпляр настроек
app_settings = AppSettings()

# Создаем хранилище
storage = MemorySettingsStorage()

# Создаем менеджер настроек
settings_manager = SettingsManager(settings_instance=app_settings, storage=storage)


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
settings_router = create_settings_router(settings_manager)
app.include_router(settings_router)


@app.get("/")
async def root():
    return {"message": "Settings Management API"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
