from abc import ABC, abstractmethod
from typing import Any


class SettingsStorage(ABC):
    """Абстрактный класс для хранения настроек"""

    @abstractmethod
    async def get_all(self) -> dict[str, Any]:
        """Получить все настройки"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Установить значение настройки"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Удалить настройку"""
        pass

    @abstractmethod
    async def delete_all(self) -> None:
        """Удалить все настройки"""
        pass
