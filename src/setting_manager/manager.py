import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .storage.base import SettingsStorage

logger = logging.getLogger(__name__)


class SettingInfo(BaseModel):
    name: str
    value: Any
    source: str  # "database", "environment", "default"
    description: str = ""
    type: str
    default_value: Any
    environment_value: Any
    can_reset: bool
    is_sensitive: bool
    allow_change: bool
    section: str
    required_role: str | None


class SettingsManager:
    """
    Менеджер настроек для работы с BaseSettings и произвольным хранилищем
    """

    def __init__(self, settings_instance: BaseSettings, storage: SettingsStorage | None = None):
        self.settings = settings_instance
        self._storage: SettingsStorage | None = storage
        self._settings_class = type(settings_instance)

        # Создаем экземпляр без данных из базы для получения environment/default значений
        self._clean_instance = self._settings_class()
        self._environment_fields_set = self._clean_instance.model_fields_set

        # Кэшируем environment и default значения
        self._environment_values: dict[str, Any] = {}
        self._default_values: dict[str, Any] = {}

        # Callback-функции для настроек
        self._callbacks: dict[str, list[Callable]] = {}

        for field_name, field_info in self._settings_class.model_fields.items():
            self._default_values[field_name] = field_info.default
            self._environment_values[field_name] = (
                getattr(self._clean_instance, field_name) if field_name in self._environment_fields_set else None
            )

    @property
    def storage(self) -> SettingsStorage:
        if self._storage is None:
            raise RuntimeError("Storage is not initialized. Please call initialize(storage=...) first.")
        return self._storage

    def on_change(self, field_name: str):
        """Декоратор для регистрации callback-функции"""

        def decorator(func: Callable):
            self.add_callback(field_name, func)
            return func

        return decorator

    def add_callback(self, field_name: str, callback: Callable) -> None:
        """Добавляет callback-функцию для настройки"""
        if field_name not in self._callbacks:
            self._callbacks[field_name] = []
        self._callbacks[field_name].append(callback)

    def remove_callback(self, field_name: str, callback: Callable) -> None:
        """Удаляет callback-функцию для настройки"""
        if field_name in self._callbacks:
            self._callbacks[field_name] = [cb for cb in self._callbacks[field_name] if cb != callback]
            if not self._callbacks[field_name]:
                del self._callbacks[field_name]

    async def initialize(self, storage: SettingsStorage | None = None) -> None:
        """Инициализация - загрузка настроек из хранилища"""
        if storage:
            self._storage = storage
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

    async def get_settings_with_sources(self, user_role: str | None = None) -> list[SettingInfo]:
        """Возвращает список всех настроек с информацией об источниках"""
        settings_info = []

        # Получаем актуальные настройки из базы
        db_settings = await self.storage.get_all()

        for field_name, field_info in self._settings_class.model_fields.items():
            current_value = getattr(self.settings, field_name)
            default_value = self._default_values[field_name]
            environment_value = self._environment_values[field_name]

            # Проверяем, является ли поле чувствительным
            is_sensitive = self._is_sensitive_field(field_name, field_info)

            # Получаем required_role для настройки
            required_role = self._get_required_role(field_info)

            # Маскируем значения для отображения, если поле чувствительное
            display_value = self._mask_sensitive_value(current_value) if is_sensitive else current_value
            display_default = self._mask_sensitive_value(default_value) if is_sensitive else default_value
            display_environment = self._mask_sensitive_value(environment_value) if is_sensitive else environment_value

            # Определяем источник
            if field_name in db_settings:
                source = "database"
                can_reset = True
            elif field_name in self._environment_fields_set:
                source = "environment"
                can_reset = False
            else:
                source = "default"
                can_reset = False

            settings_info.append(
                SettingInfo(
                    name=field_name,
                    value=display_value,
                    source=source,
                    description=field_info.description or "(no description)",
                    type=self._get_type_name(field_info.annotation),
                    default_value=display_default,
                    environment_value=display_environment,
                    can_reset=can_reset,
                    is_sensitive=is_sensitive,
                    allow_change=self._get_allow_change(field_name, field_info, user_role),
                    section=self._get_section(field_info),
                    required_role=required_role if required_role != user_role else None,
                )
            )

        return settings_info

    async def get_settings_grouped_by_sections(self, user_role: str | None = None) -> dict[str, list[SettingInfo]]:
        """Возвращает настройки сгруппированные по секциям"""
        settings = await self.get_settings_with_sources(user_role)
        grouped = {}

        for setting in settings:
            if setting.section not in grouped:
                grouped[setting.section] = []
            grouped[setting.section].append(setting)

        # Сортируем секции по алфавиту, но "System" всегда первая
        sorted_sections = sorted(grouped.keys(), key=lambda x: (x != "System", x))
        return {section: grouped[section] for section in sorted_sections}

    def _get_type_name(self, annotation: Any) -> str:
        """Получает читаемое имя типа"""
        if annotation is None:
            return "str"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation)

    async def update_setting(self, key: str, value: Any, user_role: str | None = None) -> None:
        """Обновляет настройку в хранилище и в экземпляре"""
        if not hasattr(self.settings, key):
            raise ValueError(f"Setting '{key}' does not exist")

        # Проверяем разрешение на изменение
        field_info = self._settings_class.model_fields[key]

        allow_change = self._get_allow_change(key, field_info, user_role)
        if not allow_change:
            raise ValueError(f"Setting '{key}' cannot be changed")

        # Получаем старое значение
        old_value = getattr(self.settings, key)

        # Обновляем в экземпляре
        setattr(self.settings, key, value)

        # Сохраняем в хранилище
        await self.storage.set(key, value)

        # Выполняем callback-функции
        await self._execute_callback(key, old_value, value)

    async def reset_setting(self, key: str, user_role: str | None = None) -> dict[str, Any]:
        """Сбрасывает настройку - удаляет из хранилища"""
        if not hasattr(self.settings, key):
            raise ValueError(f"Setting '{key}' does not exist")

        field_info = self._settings_class.model_fields[key]
        allow_change = self._get_allow_change(key, field_info, user_role)
        if not allow_change:
            raise ValueError(f"Setting '{key}' cannot be changed")

        # Получаем старое значение
        old_value = getattr(self.settings, key)

        await self.storage.delete(key)

        # Устанавливаем актуальное значение из environment/default
        clean_value = getattr(self._clean_instance, key)
        setattr(self.settings, key, clean_value)

        # Выполняем callback-функции
        await self._execute_callback(key, old_value, clean_value)

        return {"value": clean_value, "source": "environment" if key in self._environment_fields_set else "default"}

    async def reset_all_settings(self, user_role: str | None = None) -> None:
        """Сбрасывает все настройки - очищает хранилище"""
        # Собираем старые значения и проверяем доступ для всех настроек
        old_values = {}

        for field_name in self._settings_class.model_fields.keys():
            field_info = self._settings_class.model_fields[field_name]
            # Проверяем доступ только для тех полей, которые можно сбросить
            if self._get_allow_change(field_name, field_info, user_role):
                old_values[field_name] = getattr(self.settings, field_name)
                await self.storage.delete(field_name)
                clean_value = getattr(self._clean_instance, field_name)
                setattr(self.settings, field_name, clean_value)

        # Выполняем callback-функции для всех измененных полей
        for field_name, old_value in old_values.items():
            new_value = getattr(self.settings, field_name)
            if old_value != new_value:
                await self._execute_callback(field_name, old_value, new_value)

    def get_setting(self, key: str) -> Any:
        """Получить значение настройки"""
        return getattr(self.settings, key)

    def _is_sensitive_field(self, field_name: str, field_info: Any = None) -> bool:
        """Проверяет, является ли поле чувствительным (содержит secret, token, password)"""
        # Сначала проверяем явное указание в json_schema_extra
        if field_info:
            json_schema_extra = getattr(field_info, "json_schema_extra", None)
            if json_schema_extra and isinstance(json_schema_extra, dict):
                if "sensitive" in json_schema_extra:
                    return bool(json_schema_extra["sensitive"])

        sensitive_keywords = ["secret", "token", "password", "key"]
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)

    def _mask_sensitive_value(self, value: Any) -> Any:
        """Маскирует чувствительные значения"""
        if value is None:
            return None
        if isinstance(value, str) and value:
            return "•" * 8  # 8 точек для маскировки
        elif isinstance(value, (int, float)):
            return "•" * 8
        elif isinstance(value, bool):
            return "•" * 8
        elif isinstance(value, (list, tuple)):
            return ["•" * 8] * min(len(value), 3)  # Маскируем до 3 элементов
        else:
            return "•" * 8

    def _get_allow_change(self, field_name: str, field_info: Any, user_role: str | None = None) -> bool:
        """Получает разрешение на изменение настройки"""
        # Проверяем, является ли поле чувствительным
        is_sensitive = self._is_sensitive_field(field_name, field_info)

        # По умолчанию: чувствительные поля нельзя изменять, обычные можно
        default_allow_change = not is_sensitive

        # Проверяем явное указание allow_change в json_schema_extra
        allow_change = default_allow_change
        json_schema_extra = getattr(field_info, "json_schema_extra", None)
        if json_schema_extra and isinstance(json_schema_extra, dict):
            if "allow_change" in json_schema_extra:
                allow_change = json_schema_extra["allow_change"]

        if not allow_change:
            return False

        # Проверяем required_role
        required_role = self._get_required_role(field_info)
        if required_role and user_role != required_role:
            return False

        return True

    def _get_section(self, field_info: Any) -> str:
        """Получает секцию настройки"""
        # По умолчанию "General"
        section = "System"

        # Проверяем указание section в json_schema_extra
        json_schema_extra = getattr(field_info, "json_schema_extra", None)
        if json_schema_extra and isinstance(json_schema_extra, dict):
            if "section" in json_schema_extra:
                section = json_schema_extra["section"]

        return section

    def _get_callback(self, field_name: str) -> Callable | None:
        """Получает callback-функцию для настройки"""
        field_info = self._settings_class.model_fields[field_name]
        json_schema_extra = getattr(field_info, "json_schema_extra", None)
        if json_schema_extra and isinstance(json_schema_extra, dict):
            if "on_change" in json_schema_extra:
                return json_schema_extra["on_change"]
        return None

    async def _execute_callback(self, field_name: str, old_value: Any, new_value: Any) -> None:
        """Выполняет callback-функцию для настройки"""
        # Получаем callback из json_schema_extra
        callback = self._get_callback(field_name)

        # Также проверяем зарегистрированные callbacks
        callbacks = self._callbacks.get(field_name, [])

        if callback:
            callbacks = [callback] + callbacks

        if not callbacks:
            return

        for callback_func in callbacks:
            try:
                if inspect.iscoroutinefunction(callback_func):
                    # Асинхронная функция
                    await callback_func(old_value, new_value)
                else:
                    # Синхронная функция
                    callback_func(old_value, new_value)
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение
                logger.info(f"Error executing callback for {field_name}: {e}")

    def _get_required_role(self, field_info: Any) -> str | None:
        """Получает требуемую роль для изменения настройки"""
        json_schema_extra = getattr(field_info, "json_schema_extra", None)
        if json_schema_extra and isinstance(json_schema_extra, dict):
            if "required_role" in json_schema_extra:
                return json_schema_extra["required_role"]
        return None
