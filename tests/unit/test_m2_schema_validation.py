"""Test M2 JSON schema validation."""

import json
import pytest
from pathlib import Path
import jsonschema


class TestM2SchemaFiles:
    """Test M2 schema files exist and are valid."""
    
    @pytest.fixture
    def schema_dir(self):
        """Get schema directory path."""
        return Path(__file__).parent.parent.parent / "src" / "dicewars" / "transport" / "json" / "schema"
    
    def test_turn_context_schema_exists(self, schema_dir):
        """Test turn_context.json schema exists."""
        schema_path = schema_dir / "turn_context.json"
        assert schema_path.exists()
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        # Validate it's a proper JSON schema
        jsonschema.Draft7Validator.check_schema(schema)
    
    def test_action_result_schema_exists(self, schema_dir):
        """Test action_result.json schema exists."""
        schema_path = schema_dir / "action_result.json"
        assert schema_path.exists()
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        # Validate it's a proper JSON schema
        jsonschema.Draft7Validator.check_schema(schema)
    
    def test_capabilities_schema_exists(self, schema_dir):
        """Test capabilities.json schema exists."""
        schema_path = schema_dir / "capabilities.json"
        assert schema_path.exists()
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        # Validate it's a proper JSON schema
        jsonschema.Draft7Validator.check_schema(schema)


class TestTurnContextSchema:
    """Test TurnContext schema validation."""
    
    @pytest.fixture
    def schema(self):
        """Load turn_context schema."""
        schema_path = Path(__file__).parent.parent.parent / "src" / "dicewars" / "transport" / "json" / "schema" / "turn_context.json"
        with open(schema_path) as f:
            return json.load(f)
    
    def test_valid_turn_context(self, schema):
        """Test valid TurnContext validates."""
        # Create minimal valid turn context data
        valid_data = {
            "game_state": {
                "owners": [0, 1, 0],
                "dice": [3, 2, 4],
                "active_player_id": 1,
                "phase": "attack",
                "turn_number": 5,
                "tick_id": "123456789"
            },
            "valid_actions": [
                {
                    "type": "attack",
                    "attacker_territory_id": 1,
                    "defender_territory_id": 0,
                    "attack_index": 0
                },
                {
                    "type": "end_turn"
                }
            ]
        }
        
        # Should not raise exception
        jsonschema.validate(valid_data, schema)
    
    def test_invalid_turn_context_missing_required(self, schema):
        """Test invalid TurnContext missing required fields."""
        invalid_data = {
            "current_player": 1,
            # Missing other required fields
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data, schema)
    
    def test_turn_context_no_additional_properties(self, schema):
        """Test TurnContext rejects additional properties."""
        invalid_data = {
            "current_player": 1,
            "phase": "attack",
            "turn_number": 5,
            "state": {
                "territories": [],
                "players": [],
                "current_player": 1,
                "turn_number": 5,
                "phase": "attack",
                "game_over": False,
                "winner": None,
                "layout_hash": "12345",
                "position_hash": "67890",
                "state_hash": "11111"
            },
            "available_attacks": [],
            "tick_id": "123456789",
            "layout_hash": "12345",
            "position_hash": "67890",
            "unexpected_field": "should_fail"  # Additional property
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data, schema)


class TestActionResultSchema:
    """Test ActionResult schema validation."""
    
    @pytest.fixture
    def schema(self):
        """Load action_result schema."""
        schema_path = Path(__file__).parent.parent.parent / "src" / "dicewars" / "transport" / "json" / "schema" / "action_result.json"
        with open(schema_path) as f:
            return json.load(f)
    
    def test_valid_action_result(self, schema):
        """Test valid ActionResult validates."""
        valid_data = {
            "success": True,
            "tick_id": "123456789",
            "state_hash": "987654321",
            "position_hash": "555666777",  # v5 requirement: always present
            "new_game_state": {
                "owners": [0, 1, 0],
                "dice": [3, 2, 4],
                "active_player_id": 1,
                "phase": "attack",
                "turn_number": 5,
                "tick_id": "123456789"
            },
            "battle_result": None,
            "delta": {
                "changed_territories": [1, 2],
                "new_owners": [0, 1],
                "new_dice": [3, 2]
            },
            "error_code": None,
            "error_data": None
        }
        
        # Should not raise exception
        jsonschema.validate(valid_data, schema)
    
    def test_action_result_requires_position_hash(self, schema):
        """Test ActionResult requires position_hash (v5)."""
        invalid_data = {
            "success": True,
            "tick_id": "123456789",
            "state_hash": "987654321",
            # Missing position_hash - required in v5
            "new_game_state": {
                "territories": [],
                "players": [],
                "current_player": 1,
                "turn_number": 5,
                "phase": "attack",
                "game_over": False,
                "winner": None,
                "layout_hash": "12345",
                "position_hash": "67890",
                "state_hash": "11111"
            }
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data, schema)


class TestCapabilitiesSchema:
    """Test Capabilities schema validation."""
    
    @pytest.fixture
    def schema(self):
        """Load capabilities schema."""
        schema_path = Path(__file__).parent.parent.parent / "src" / "dicewars" / "transport" / "json" / "schema" / "capabilities.json"
        with open(schema_path) as f:
            return json.load(f)
    
    def test_valid_capabilities(self, schema):
        """Test valid Capabilities validates."""
        valid_data = {
            "rules_version": "1.0",
            "schema_version": "5.0",
            "map_name": "test_map",
            "num_players": 4,
            "num_territories": 6,
            "layout_hash": "123456789",
            "action_index_hash": "987654321",
            "winner_policy": "most_territories",
            "winner_tiebreak_chain": ["territories", "total_dice"],
            "max_turns": 100,
            "max_dice_per_territory": 8,
            "supports_delta": True,
            "supports_penalties": True,
            "uint64_encoding": "decimal"
        }
        
        # Should not raise exception
        jsonschema.validate(valid_data, schema)
    
    def test_capabilities_uint64_pattern(self, schema):
        """Test Capabilities enforces uint64 decimal pattern."""
        invalid_data = {
            "layout_hash": "not_a_number",  # Should be decimal string
            "action_index_hash": "987654321",
            "supports_v5": True,
            "supports_penalty_actions": True,
            "supports_observer_api": True,
            "max_players": 8,
            "timeout_ms": 30000
        }
        
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_data, schema)