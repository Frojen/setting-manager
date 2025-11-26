import pytest

from setting_manager import SettingsManager
from tests.conftest import (
    ADMIN_ROLE,
    DEVELOPER_ROLE,
    REGULAR_USER_ROLE,
    SUPERUSER_ROLE,
    TESTER_ROLE,
)


async def test_immutable_setting(manager: SettingsManager):
    """Тест: Никто, даже суперпользователь, не может изменить 'immutable' настройку."""
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("environment", "staging", user_role=SUPERUSER_ROLE)
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("environment", "staging", user_role=ADMIN_ROLE)


async def test_required_role_string(manager: SettingsManager):
    """Тест: Доступ к настройке с required_role: 'admin'."""
    # Успешный кейс
    await manager.update_setting("admin_email", "new@test.com", user_role=ADMIN_ROLE)
    assert manager.get_setting("admin_email") == "new@test.com"

    # Неуспешный кейс
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("admin_email", "hacker@test.com", user_role=DEVELOPER_ROLE)


async def test_required_role_list(manager: SettingsManager):
    """Тест: Доступ к настройке с required_role: ['developer', 'tester']."""
    # Успешные кейсы
    await manager.update_setting("feature_flags", ["feat1"], user_role=DEVELOPER_ROLE)
    assert manager.get_setting("feature_flags") == ["feat1"]

    await manager.update_setting("feature_flags", ["feat2"], user_role=TESTER_ROLE)
    assert manager.get_setting("feature_flags") == ["feat2"]

    # Неуспешный кейс
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("feature_flags", ["feat3"], user_role=ADMIN_ROLE)


async def test_allow_change_false(manager: SettingsManager):
    """Тест: Суперпользователь может менять настройку с 'allow_change: False', а обычный пользователь - нет."""
    # Успешный кейс (суперпользователь)
    await manager.update_setting("service_host", "remote_host", user_role=SUPERUSER_ROLE)
    assert manager.get_setting("service_host") == "remote_host"

    # Неуспешный кейс (обычный пользователь)
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("service_host", "some_other_host", user_role=REGULAR_USER_ROLE)


async def test_private_setting_without_role(manager: SettingsManager):
    """Тест: Настройка без роли доступна только суперпользователю, если он задан."""
    # Успешный кейс (суперпользователь)
    await manager.update_setting("app_name", "Super App", user_role=SUPERUSER_ROLE)
    assert manager.get_setting("app_name") == "Super App"

    # Неуспешный кейс (обычный пользователь)
    with pytest.raises(ValueError, match="cannot be changed"):
        await manager.update_setting("app_name", "Regular App", user_role=ADMIN_ROLE)
