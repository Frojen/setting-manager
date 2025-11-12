import os
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..manager import SettingInfo, SettingsManager


def create_settings_router(  # noqa: C901
    settings_manager: SettingsManager, router_prefix: str = "/setting-manager", template_dir: str | None = None
) -> APIRouter:
    """
    Создает роутер FastAPI для управления настройками
    """
    router = APIRouter(prefix=router_prefix, tags=["settings"])

    # Настройка шаблонов
    if template_dir is None:
        template_dir = os.path.join(os.path.dirname(__file__), "templates")

    templates = Jinja2Templates(directory=template_dir)

    @router.get("/", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """Страница управления настройками"""
        settings_info = await settings_manager.get_settings_with_sources()
        return templates.TemplateResponse(
            "settings.html", {"request": request, "settings": settings_info, "router_prefix": router_prefix}
        )

    @router.get("/settings", response_model=list[SettingInfo])
    async def get_settings():
        """API для получения настроек"""
        return await settings_manager.get_settings_with_sources()

    @router.post("/{setting_name}")
    async def update_setting(setting_name: str, value: str = Form(...)):
        """Обновить настройку"""
        try:
            # Конвертируем значение к правильному типу
            current_value = settings_manager.get_setting(setting_name)
            converted_value = convert_value(value, type(current_value))

            await settings_manager.update_setting(setting_name, converted_value)
            return {"status": "success", "message": f"Setting {setting_name} updated"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/{setting_name}")
    async def reset_setting(setting_name: str):
        """Сбросить настройку"""
        try:
            result = await settings_manager.reset_setting(setting_name)
            return {"status": "success", "message": f"Setting {setting_name} reset", **result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/actions/reset-all")
    async def reset_all_settings():
        """Сбросить все настройки"""
        try:
            await settings_manager.reset_all_settings()
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
