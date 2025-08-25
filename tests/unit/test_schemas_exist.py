"""Test JSON schema files exist and are valid."""

import json
from pathlib import Path

import pytest


def get_schema_dir() -> Path:
    """Get the schema directory path."""
    import dicewars.transport.json.schema as schema_module

    return Path(schema_module.__file__).parent


def test_schema_files_exist():
    """Test that required schema files exist."""
    schema_dir = get_schema_dir()
    required_schemas = [
        "turn_context.json",
        "action_result.json",
        "capabilities.json",
        "map_layout.json",
    ]

    for schema_file in required_schemas:
        schema_path = schema_dir / schema_file
        assert schema_path.exists(), f"Missing schema: {schema_file}"


def test_schemas_are_valid_json():
    """Test that schema files contain valid JSON."""
    schema_dir = get_schema_dir()

    for schema_file in schema_dir.glob("*.json"):
        if schema_file.stat().st_size == 0:
            # Empty stub files are OK in M0
            continue

        with open(schema_file) as f:
            try:
                data = json.load(f)
                # Must be a JSON Schema object
                assert isinstance(data, dict)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {schema_file}: {e}")


def test_schemas_have_additional_properties_false():
    """Test that all schemas set additionalProperties: false."""
    schema_dir = get_schema_dir()

    for schema_file in schema_dir.glob("*.json"):
        if schema_file.stat().st_size == 0:
            continue  # Skip empty stubs

        with open(schema_file) as f:
            schema = json.load(f)

        # For non-empty schemas, check additionalProperties
        if schema:
            assert schema.get("additionalProperties") is False, (
                f"Schema {schema_file} missing 'additionalProperties: false'"
            )
