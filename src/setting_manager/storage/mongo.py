from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from .base import SettingsStorage


class MongoSettingsStorage(SettingsStorage):
    """Хранилище настроек в MongoDB"""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_all(self) -> dict[str, Any]:
        """Получить все настройки из MongoDB"""
        cursor = self.collection.find()
        settings = {}

        async for doc in cursor:
            settings[doc["key"]] = doc["value"]

        return settings

    async def set(self, key: str, value: Any) -> None:
        """Установить значение настройки в MongoDB"""
        await self.collection.update_one(
            {"key": key}, {"$set": {"value": value, "updated_at": datetime.now(UTC)}}, upsert=True
        )

    async def delete(self, key: str) -> None:
        """Удалить настройку из MongoDB"""
        await self.collection.delete_one({"key": key})

    async def delete_all(self) -> None:
        """Удалить все настройки из MongoDB"""
        await self.collection.delete_many({})
