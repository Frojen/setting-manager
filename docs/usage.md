# Руководство по использованию

`setting-manager` — это гибкая библиотека для управления настройками приложения, построенная на Pydantic. Она позволяет централизованно управлять конфигурацией, используя различные источники данных, и предоставляет удобный веб-интерфейс для администрирования.

## Основные концепции

1.  **`SettingsManager`**: Центральный класс, который управляет всем процессом.
2.  **`BaseSettings`**: Настройки определяются, наследуясь от класса `pydantic_settings.BaseSettings`.
3.  **`SettingsStorage`**: Асинхронное хранилище для сохранения измененных настроек. Можно реализовать свой собственный адаптер для любой базы данных (Redis, PostgreSQL и т.д.).
4.  **Источники настроек**: Библиотека работает с тремя источниками в следующем порядке приоритета:
    *   **Хранилище (Database)**: Значения, измененные через интерфейс или API. Имеют наивысший приоритет.
    *   **Переменные окружения (Environment)**: Значения, заданные через переменные окружения.
    *   **Значения по умолчанию (Default)**: Значения, определенные в вашем классе `BaseSettings`.

## Использование

## Установка

```bash
pip install setting-manager
```

## Шаг 1: Определение настроек

Создайте класс, унаследованный от `pydantic_settings.BaseSettings`. Используйте `pydantic.Field` для добавления метаданных, которые управляют поведением настроек в `setting-manager`.

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    app_name: str = Field("My Awesome App", description="Название приложения.", json_schema_extra={"section": "General"})
    debug_mode: bool = Field(False, description="Включает режим отладки.", json_schema_extra={"section": "General"})
    secret_key: str = Field(..., description="Секретный ключ.", json_schema_extra={"sensitive": True, "section": "Security"})
    admin_role: str = Field("admin", description="Роль для доступа к изменению.", json_schema_extra={"required_role": "admin", "section": "Security"})
```

**Метаданные `json_schema_extra`:**

*   `section: str`: Группирует настройки в веб-интерфейсе.
*   `immutable: bool`: Если `True`, настройку не может изменить **никто**, даже суперпользователь.
*   `allow_change: bool`: Если `False`, настройку не могут менять обычные пользователи (но может суперпользователь).
*   `required_role: str | list[str]`: Задает роль (или список ролей), необходимую для изменения настройки.
*   `sensitive: bool`: Помечает настройку как чувствительную (например, пароль или токен). Ее значение будет маскироваться в интерфейсе.

Полный пример определения класса `AppSettings` со всеми вариантами метаданных можно найти в файле:
**[`examples/fastapi_example.py`](../examples/fastapi_example.py)**.

## Шаг 2: Инициализация менеджера

Для работы `SettingsManager` требуется экземпляр вашего класса настроек и адаптер хранилища.

```python
# Ключевые моменты инициализации
from setting_manager import SettingsManager

# ... (определение AppSettings и Storage)

# Инициализируем менеджер с ролью суперпользователя
manager = SettingsManager(
    settings_instance=settings,
    storage=storage,
    superuser_role="superuser",
)
await manager.initialize()
```

## Шаг 3: Интеграция с FastAPI

Библиотека предоставляет готовую функцию `create_settings_router` для быстрой интеграции с FastAPI.

**Ключевые параметры:**

*   `settings_manager`: Экземпляр вашего `SettingsManager`.
*   `security_dependency`: Зависимость FastAPI, которая должна возвращать роль текущего пользователя. Это позволяет интегрировать `setting-manager` с вашей системой аутентификации.
*   `superuser_role`: Название роли суперпользователя.

После подключения роутера можно перейти по адресу, который указан в `prefix`, и управлять настройками через веб-интерфейс.

 ## Дополнительно

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


### Система прав доступа

Система прав доступа построена на нескольких правилах, которые проверяются в строгом порядке:

1.  **`immutable: true`**: Если установлено, изменение **запрещено всем**, включая суперпользователя. Это наивысший приоритет.
2.  **Суперпользователь**: Если роль пользователя совпадает с `superuser_role`, ему **разрешено** изменять любую настройку (кроме `immutable`).
3.  **Обычный пользователь**:
    *   Если у настройки есть `required_role`, пользователь должен иметь одну из указанных ролей.
    *   Если в системе **включен режим суперпользователя**, то все настройки без `required_role` становятся "приватными" и недоступны для изменения обычными пользователями.
    *   Если у настройки стоит `allow_change: false`, обычный пользователь не может ее изменить.

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
