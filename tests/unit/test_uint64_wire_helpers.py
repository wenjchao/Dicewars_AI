"""Test uint64 wire format helpers for v5 compatibility."""

import json

import pytest


def test_uint64_decimal_string_format():
    """Test uint64 values serialize as decimal strings."""
    # These are the wire format helpers that will be used throughout

    def uint64_to_wire(value: int) -> str:
        """Convert uint64 to wire format (decimal string)."""
        if not isinstance(value, int):
            raise TypeError("Expected int")
        if value < 0:
            raise ValueError("uint64 must be non-negative")
        if value >= 2**64:
            raise ValueError("Value too large for uint64")
        return str(value)

    def wire_to_uint64(value: str) -> int:
        """Convert wire format to uint64."""
        if not isinstance(value, str):
            raise TypeError("Expected string")
        if not value.isdigit():
            raise ValueError("Must be decimal digits only")
        result = int(value)
        if result >= 2**64:
            raise ValueError("Value too large for uint64")
        return result

    # Test valid conversions
    test_cases = [0, 1, 42, 1337, 2**32, 2**63 - 1, 2**64 - 1]

    for value in test_cases:
        wire = uint64_to_wire(value)
        assert isinstance(wire, str)
        assert wire.isdigit()
        assert wire_to_uint64(wire) == value

    # Test invalid cases
    with pytest.raises(ValueError):
        uint64_to_wire(-1)

    with pytest.raises(ValueError):
        uint64_to_wire(2**64)

    with pytest.raises(ValueError):
        wire_to_uint64("not_a_number")

    with pytest.raises(ValueError):
        wire_to_uint64("-1")


def test_json_roundtrip_uint64_fields():
    """Test that uint64 fields survive JSON roundtrip."""
    sample_data = {
        "tick_id": "1234567890123456789",
        "state_hash": "9876543210987654321",
        "position_hash": "1111222233334444",
        "layout_hash": "5555666677778888",
        "action_index_hash": "9999000011112222",
    }

    # Round-trip through JSON
    json_str = json.dumps(sample_data)
    parsed = json.loads(json_str)

    # All values should remain as strings
    for key, expected_value in sample_data.items():
        assert parsed[key] == expected_value
        assert isinstance(parsed[key], str)
        assert parsed[key].isdigit()
