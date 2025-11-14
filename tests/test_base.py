def test_settings_manager_version():
    """Test that version is accessible."""
    from setting_manager import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0
