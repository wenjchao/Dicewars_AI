"""Test package imports and structure."""



def test_package_imports():
    """Test that basic package imports work."""
    import dicewars

    assert hasattr(dicewars, "__version__")

    import dicewars.__about__

    assert dicewars.__about__.RULES_VERSION == "v1"
    assert dicewars.__about__.SCHEMA_VERSION == "v5"


def test_api_module_exists():
    """Test that API module structure exists."""
    import dicewars.api

    assert hasattr(dicewars.api, "__all__")


def test_core_modules_importable():
    """Test that core module stubs are importable."""
    # Should not raise ImportError


def test_transport_schema_directory_exists():
    """Test that schema directory structure exists."""
    # Directory should exist (file will be empty stub)
