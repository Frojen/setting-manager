from typing import Any

from .base import SettingsStorage


class MemorySettingsStorage(SettingsStorage):
    """Хранилище настроек в памяти"""

    def __init__(self):
        self._storage: dict[str, Any] = {}

    async def get_all(self) -> dict[str, Any]:
        """Получить все настройки из памяти"""
        return self._storage.copy()

    async def set(self, key: str, value: Any) -> None:
        """Установить значение настройки в памяти"""
        self._storage[key] = value

    async def delete(self, key: str) -> None:
        """Удалить настройку из памяти"""
        if key in self._storage:
            del self._storage[key]

    async def delete_all(self) -> None:
        """Удалить все настройки из памяти"""
        self._storage.clear()
