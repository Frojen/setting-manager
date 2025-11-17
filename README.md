# Setting Manager

Менеджер настроек для асинхронных приложений на Python, построенный на базе Pydantic.

## Основные возможности

- **Централизованное управление:** Управляйте всеми настройками вашего приложения из одного места.
- **Гибкие источники:** Загружайте настройки из базы данных, переменных окружения или используйте значения по умолчанию.
- **Интеграция с Pydantic:** Определяйте настройки с помощью `pydantic.BaseSettings`.
- **Абстрактное хранилище:** Используйте любое асинхронное хранилище, реализовав простой интерфейс `SettingsStorage`.
- **Обратные вызовы (Callbacks):** Выполняйте действия при изменении настроек.
- **Управление доступом:** Ограничивайте изменение настроек на основе ролей пользователей.
- **Безопасность:** Автоматически скрывайте чувствительные данные (пароли, токены).
- **Группировка:** Организуйте настройки по секциям для удобного отображения в интерфейсе.

## Установка

```bash
pip install setting-manager
```

## Пример использования

Ниже приведен пример использования `setting-manager` с простым хранилищем в памяти.

### 1. Определите ваши настройки

Создайте класс, унаследованный от `pydantic_settings.BaseSettings`. Вы можете использовать `Field` из Pydantic для добавления метаданных, таких как описание, секция или требуемая роль.

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    app_name: str = Field("My Awesome App", description="Название приложения.", json_schema_extra={"section": "General"})
    debug_mode: bool = Field(False, description="Включает режим отладки.", json_schema_extra={"section": "General"})
    secret_key: str = Field(..., description="Секретный ключ.", json_schema_extra={"sensitive": True, "section": "Security"})
    admin_role: str = Field("admin", description="Роль для доступа к изменению.", json_schema_extra={"required_role": "admin", "section": "Security"})
```

### 2. Создайте хранилище

Реализуйте `SettingsStorage` для вашего источника данных (например, Redis, PostgreSQL, MongoDB).

```python
from setting_manager.storage.base import SettingsStorage

class InMemoryStorage(SettingsStorage):
    def __init__(self):
        self._data = {}

    async def get_all(self) -> dict:
        return self._data.copy()

    async def set(self, key: str, value: any):
        self._data[key] = value

    async def delete(self, key: str):
        if key in self._data:
            del self._data[key]
```

### 3. Инициализируйте менеджер

```python
import asyncio
from setting_manager import SettingsManager

async def main():
    # 1. Создаем экземпляр настроек
    settings = AppSettings()

    # 2. Создаем экземпляр хранилища
    storage = InMemoryStorage()

    # 3. Создаем менеджер
    manager = SettingsManager(settings_instance=settings, storage=storage)

    # 4. Инициализируем менеджер (загружаем данные из хранилища)
    await manager.initialize()

    # 5. Получаем и выводим настройки
    all_settings = await manager.get_settings_with_sources()
    for setting in all_settings:
        print(f"- {setting.name}: {setting.value} (source: {setting.source})")

    # 6. Обновляем настройку
    print("\nUpdating app_name...")
    await manager.update_setting("app_name", "My Super App")

    # 7. Проверяем обновленное значение
    updated_settings = await manager.get_settings_with_sources()
    for setting in updated_settings:
        if setting.name == "app_name":
            print(f"- {setting.name}: {setting.value} (source: {setting.source})")


if __name__ == "__main__":
    asyncio.run(main())
```

## Продвинутое использование

### Обратные вызовы (Callbacks)

Вы можете зарегистрировать функции, которые будут вызваны при изменении значения настройки.

```python
# Функция, которая будет вызвана при изменении
async def on_debug_mode_change(old_value, new_value):
    print(f"Debug mode changed from {old_value} to {new_value}")

# Регистрация с помощью декоратора
@manager.on_change("debug_mode")
async def on_debug_mode_change_decorator(old_value, new_value):
    print(f"Debug mode changed (decorator) from {old_value} to {new_value}")


# Или вручную
manager.add_callback("debug_mode", on_debug_mode_change)

# Обновление вызовет обе функции
await manager.update_setting("debug_mode", True)
```

### Управление доступом по ролям

Вы можете указать, какая роль требуется для изменения настройки, используя `required_role` в `json_schema_extra`.

```python
class AppSettings(BaseSettings):
    # ...
    admin_email: str = Field(
        "admin@example.com",
        description="Email администратора.",
        json_schema_extra={"section": "Security", "required_role": "admin"}
    )

# Попытка изменить настройку без нужной роли вызовет ошибку
try:
    await manager.update_setting("admin_email", "new@example.com", user_role="user")
except ValueError as e:
    print(e) # "Setting 'admin_email' cannot be changed"

# А с нужной ролью - успешно
await manager.update_setting("admin_email", "new@example.com", user_role="admin")
```

### Чувствительные данные

Поля, содержащие в названии `secret`, `token`, `password` или `key`, или помеченные как `{"sensitive": True}`, будут автоматически маскироваться при отображении.

```python
settings_info = await manager.get_settings_with_sources()
secret_key_info = next(s for s in settings_info if s.name == "secret_key")
print(secret_key_info.value) # "••••••••"
```
