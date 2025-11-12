from typing import Any
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from datetime import datetime

class SettingInfo(BaseModel):
    name: str
    value: Any
    source: str  # "database", "environment", "default"
    description: str = ""
    type: str

class SettingsManager:
    def __init__(
            self,
            settings_instance: BaseSettings,
            mongo_db: AsyncIOMotorDatabase,
            collection_name: str = "app_settings"
    ):
        self.settings = settings_instance
        self.mongo_db = mongo_db
        self.settings_collection = self.mongo_db[collection_name]
        self._db_settings: dict[str, Any] = {}

    async def load_from_database(self) -> None:
        """Загружает настройки из базы данных и обновляет экземпляр"""
        # Очищаем базу от несуществующих настроек
        await self._cleanup_database()

        # Получаем настройки из базы
        self._db_settings = await self._get_database_settings()

        # Обновляем поля экземпляра настроек
        for key, value in self._db_settings.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

    async def _get_database_settings(self) -> dict[str, Any]:
        """Получает все настройки из базы данных"""
        cursor = self.settings_collection.find()
        settings = {}

        async for doc in cursor:
            settings[doc["key"]] = doc["value"]

        return settings

    async def _cleanup_database(self) -> None:
        """Удаляет из базы настройки, которых нет в классе"""
        valid_keys = set(self.settings.model_fields.keys())

        # Находим все ключи в базе
        cursor = self.settings_collection.find({}, {"key": 1})
        db_keys = set()

        async for doc in cursor:
            db_keys.add(doc["key"])

        # Удаляем невалидные ключи
        invalid_keys = db_keys - valid_keys
        if invalid_keys:
            await self.settings_collection.delete_many({"key": {"$in": list(invalid_keys)}})

    async def get_settings_info(self) -> list[SettingInfo]:
        """Возвращает список всех настроек с информацией об источниках"""
        settings_info = []

        for field_name, field_info in self.settings.model_fields.items():
            value = getattr(self.settings, field_name)

            # Определяем источник
            if field_name in self._db_settings:
                source = "database"
            elif not self.settings.model_fields[field_name].default:
                source = "environment"
            else:
                source = "default"

            settings_info.append(SettingInfo(
                name=field_name,
                value=value,
                source=source,
                description=field_info.description,
                type=field_info.annotation.__name__ if field_info.annotation else "str"
            ))

        return settings_info

    async def update_setting(self, key: str, value: Any, user: Optional[str] = None) -> None:
        """Обновляет настройку в базе данных и в экземпляре"""
        if not hasattr(self.settings, key):
            raise ValueError(f"Setting '{key}' does not exist")

        # Обновляем в экземпляре
        setattr(self.settings, key, value)

        # Сохраняем в базу (только ключ и значение)
        await self.settings_collection.update_one(
            {"key": key},
            {
                "$set": {
                    "value": value,
                    "updated_at": datetime.utcnow(),
                    "user": user
                }
            },
            upsert=True
        )

        # Обновляем кэш
        self._db_settings[key] = value

    async def reset_setting(self, key: str) -> None:
        """Сбрасывает настройку - удаляет из базы"""
        await self.settings_collection.delete_one({"key": key})

        # Удаляем из кэша
        if key in self._db_settings:
            del self._db_settings[key]

        # Перезагружаем настройки (вернет environment/default)
        await self.load_from_database()

    async def reset_all_settings(self) -> None:
        """Сбрасывает все настройки - очищает базу"""
        await self.settings_collection.delete_many({})
        self._db_settings = {}
        await self.load_from_database()