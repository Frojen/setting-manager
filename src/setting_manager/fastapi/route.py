import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..manager import SettingInfo, SettingsManager


def create_settings_router(  # noqa: C901
    settings_manager: SettingsManager,
    router_prefix: str = "/setting-manager",
    template_dir: str | None = None,
    security_dependency: Callable | None = None,
) -> APIRouter:
    """
    Создает роутер FastAPI для управления настройками

    Args:
        settings_manager: Менеджер настроек
        router_prefix: Префикс для роутов
        template_dir: Директория с шаблонами
        security_dependency: Зависимость для проверки доступа к роутам
                             Должна возвращать роль пользователя или None
    """
    # Нормализуем router_prefix
    if router_prefix.endswith("/"):
        router_prefix = router_prefix[:-1]
    if not router_prefix.startswith("/"):
        router_prefix = f"/{router_prefix}"

    router = APIRouter(prefix=router_prefix, tags=["settings"])

    # Настройка шаблонов
    if template_dir is None:
        template_dir = os.path.join(os.path.dirname(__file__), "templates")

    templates = Jinja2Templates(directory=template_dir)

    # Определяем зависимости для эндпоинтов
    def get_user_role_dependency():
        """Возвращает зависимость для получения роли пользователя или None"""
        return Depends(security_dependency) if security_dependency else None

    @router.get("/", response_class=HTMLResponse)
    async def settings_page(request: Request, user_role: str | None = get_user_role_dependency()):
        """Страница управления настройками"""
        settings_grouped = await settings_manager.get_settings_grouped_by_sections(user_role)
        return templates.TemplateResponse(
            "grouped_settings.html",
            {
                "request": request,
                "settings_grouped": settings_grouped,
                "router_prefix": router_prefix,
                "user_role": user_role,
            },
        )

    @router.get("/settings", response_model=dict[str, list[SettingInfo]])
    async def get_settings(user_role: str | None = get_user_role_dependency()):
        """API для получения настроек сгруппированных по секциям"""
        return await settings_manager.get_settings_grouped_by_sections(user_role)

    @router.post("/{setting_name}")
    async def update_setting(
        setting_name: str, value: str = Form(...), user_role: str | None = get_user_role_dependency()
    ):
        """Обновить настройку"""
        try:
            # Конвертируем значение к правильному типу
            current_value = settings_manager.get_setting(setting_name)
            converted_value = convert_value(value, type(current_value))

            await settings_manager.update_setting(setting_name, converted_value, user_role)
            return {"status": "success", "message": f"Setting {setting_name} updated"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/{setting_name}")
    async def reset_setting(setting_name: str, user_role: str | None = get_user_role_dependency()):
        """Сбросить настройку"""
        try:
            result = await settings_manager.reset_setting(setting_name, user_role)
            return {"status": "success", "message": f"Setting {setting_name} reset", **result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/actions/reset-all")
    async def reset_all_settings(user_role: str | None = get_user_role_dependency()):
        """Сбросить все настройки"""
        try:
            await settings_manager.reset_all_settings(user_role)
            return {"status": "success", "message": "All settings reset"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router


def convert_value(value: str, target_type: type) -> Any:
    """Конвертирует строковое значение к целевому типу"""
    if value == "":
        return None

    if target_type is bool:
        return value.lower() in ("true", "1", "yes", "on", "y")
    elif target_type is int:
        return int(value)
    elif target_type is float:
        return float(value)
    elif target_type is list:
        return [item.strip() for item in value.split(",")]
    else:
        return value
