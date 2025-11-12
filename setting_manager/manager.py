from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .storage.base import SettingsStorage


class SettingInfo(BaseModel):
    name: str
    value: Any
    source: str  # "database", "environment", "default"
    description: str = ""
    type: str
    default_value: Any = None
    environment_value: Any = None
    can_reset: bool = False


class SettingsManager:
    """
    Менеджер настроек для работы с BaseSettings и произвольным хранилищем
    """

    def __init__(self, settings_instance: BaseSettings, storage: SettingsStorage):
        self.settings = settings_instance
        self.storage = storage
        self._settings_class = type(settings_instance)

        # Создаем экземпляр без данных из базы для получения environment/default значений
        self._clean_instance = self._settings_class()
        self._environment_fields_set = self._clean_instance.model_fields_set

        # Кэшируем environment и default значения
        self._environment_values: dict[str, Any] = {}
        self._default_values: dict[str, Any] = {}

        for field_name, field_info in self._settings_class.model_fields.items():
            self._default_values[field_name] = field_info.default
            self._environment_values[field_name] = (
                getattr(self._clean_instance, field_name) if field_name in self._environment_fields_set else None
            )

    async def initialize(self) -> None:
        """Инициализация - загрузка настроек из хранилища"""
        await self.load_from_storage()

    async def load_from_storage(self) -> None:
        """Загружает настройки из хранилища и обновляет экземпляр"""
        # Получаем настройки из хранилища
        db_settings = await self.storage.get_all()

        # Очищаем хранилище от несуществующих настроек
        await self._cleanup_storage(db_settings)

        # Обновляем поля экземпляра настроек
        for key, value in db_settings.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

    async def _cleanup_storage(self, db_settings: dict[str, Any]) -> None:
        """Удаляет из хранилища настройки, которых нет в классе"""
        valid_keys = set(self._settings_class.model_fields.keys())
        db_keys = set(db_settings.keys())

        # Удаляем невалидные ключи
        invalid_keys = db_keys - valid_keys
        for key in invalid_keys:
            await self.storage.delete(key)

    async def get_settings_with_sources(self) -> list[SettingInfo]:
        """Возвращает список всех настроек с информацией об источниках"""
        settings_info = []

        # Получаем актуальные настройки из базы
        db_settings = await self.storage.get_all()

        for field_name, field_info in self._settings_class.model_fields.items():
            current_value = getattr(self.settings, field_name)
            default_value = self._default_values[field_name]
            environment_value = self._environment_values[field_name]

            # Определяем источник
            if field_name in db_settings:
                source = "database"
                can_reset = True
            elif current_value != default_value:
                source = "environment"
                can_reset = False
            else:
                source = "default"
                can_reset = False

            settings_info.append(
                SettingInfo(
                    name=field_name,
                    value=current_value,
                    source=source,
                    description=field_info.description or "(no description)",
                    type=self._get_type_name(field_info.annotation),
                    default_value=default_value,
                    environment_value=environment_value,
                    can_reset=can_reset,
                )
            )

        return settings_info

    def _get_type_name(self, annotation: Any) -> str:
        """Получает читаемое имя типа"""
        if annotation is None:
            return "str"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation)

    async def update_setting(self, key: str, value: Any) -> None:
        """Обновляет настройку в хранилище и в экземпляре"""
        if not hasattr(self.settings, key):
            raise ValueError(f"Setting '{key}' does not exist")

        # Обновляем в экземпляре
        setattr(self.settings, key, value)

        # Сохраняем в хранилище
        await self.storage.set(key, value)

    async def reset_setting(self, key: str) -> dict[str, Any]:
        """Сбрасывает настройку - удаляет из хранилища"""
        await self.storage.delete(key)

        # Устанавливаем актуальное значение из environment/default
        clean_value = getattr(self._clean_instance, key)
        setattr(self.settings, key, clean_value)

        return {"value": clean_value, "source": "environment" if key in self._environment_fields_set else "default"}

    async def reset_all_settings(self) -> None:
        """Сбрасывает все настройки - очищает хранилище"""
        await self.storage.delete_all()

        # Восстанавливаем все значения из environment/default
        for field_name in self._settings_class.model_fields.keys():
            clean_value = getattr(self._clean_instance, field_name)
            setattr(self.settings, field_name, clean_value)

    def get_setting(self, key: str) -> Any:
        """Получить значение настройки"""
        return getattr(self.settings, key)
