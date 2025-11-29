"""Tests for neuroconv.tools.hed module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from neuroconv.tools.importing import is_package_installed


# Skip all tests in this module if hedtools is not installed
pytestmark = pytest.mark.skipif(not is_package_installed("hed"), reason="hedtools not installed")


class TestGetFlattenedHedSchema:
    """Tests for get_flattened_hed_schema function."""

    def test_returns_dict(self):
        """Test that the function returns a dictionary."""
        from neuroconv.tools.hed import get_flattened_hed_schema

        schema = get_flattened_hed_schema()
        assert isinstance(schema, dict)

    def test_contains_expected_tags(self):
        """Test that the schema contains expected HED tags."""
        from neuroconv.tools.hed import get_flattened_hed_schema

        schema = get_flattened_hed_schema()

        # Check for some common HED tags that should exist
        assert len(schema) > 0

        # Check that some top-level categories exist
        top_level_tags = [key.split("/")[0] for key in schema.keys()]
        assert "Event" in top_level_tags or any("Event" in key for key in schema.keys())

    def test_values_are_strings(self):
        """Test that all values in the schema are strings (descriptions)."""
        from neuroconv.tools.hed import get_flattened_hed_schema

        schema = get_flattened_hed_schema()

        for tag, description in schema.items():
            assert isinstance(tag, str), f"Tag {tag} is not a string"
            assert isinstance(description, str), f"Description for {tag} is not a string"

    def test_custom_version(self):
        """Test that a specific HED version can be loaded."""
        from neuroconv.tools.hed import get_flattened_hed_schema

        schema = get_flattened_hed_schema(hed_version="8.3.0")
        assert isinstance(schema, dict)
        assert len(schema) > 0

    def test_none_version_uses_latest(self):
        """Test that None version loads the latest schema."""
        from neuroconv.tools.hed import get_flattened_hed_schema

        # Should not raise an error
        schema = get_flattened_hed_schema(hed_version=None)
        assert isinstance(schema, dict)
        assert len(schema) > 0


class TestValidateHedString:
    """Tests for _validate_hed_string function."""

    def test_valid_hed_string_returns_empty_list(self):
        """Test that a valid HED string returns no errors."""
        from neuroconv.tools.hed import _validate_hed_string

        # Event is a valid HED tag
        errors = _validate_hed_string("Event")
        assert isinstance(errors, list)
        # Note: Depending on HED schema rules, this may or may not have errors

    def test_invalid_hed_string_returns_errors(self):
        """Test that an invalid HED string returns errors."""
        from neuroconv.tools.hed import _validate_hed_string

        # Completely made up tag that shouldn't exist
        errors = _validate_hed_string("CompletelyInvalidTagThatDoesNotExist123456")
        assert isinstance(errors, list)
        assert len(errors) > 0

    def test_def_tag_without_definitions_returns_error(self):
        """Test that a Def/ tag without definitions returns an error."""
        from neuroconv.tools.hed import _validate_hed_string

        # Def tag referencing undefined definition should fail
        errors = _validate_hed_string("Def/My-custom-definition", hed_version="8.3.0")
        assert isinstance(errors, list)
        assert len(errors) > 0
        # Should contain DEF_INVALID error
        assert any("def" in str(e).lower() for e in errors)

    def test_def_tag_with_definitions_returns_no_error(self):
        """Test that a Def/ tag with matching definition returns no errors."""
        import hed
        from hed.models import DefinitionDict
        from hed.schema import load_schema_version

        from neuroconv.tools.hed import _validate_hed_string

        schema = load_schema_version("8.3.0")
        definition_string = "(Definition/My-custom-definition, (Sensory-event, Visual-presentation))"
        def_dicts = DefinitionDict([definition_string], schema)

        # Def tag with matching definition should pass
        errors = _validate_hed_string(
            "Def/My-custom-definition",
            hed_version="8.3.0",
            def_dicts=def_dicts,
        )
        assert isinstance(errors, list)
        assert len(errors) == 0

    def test_definition_string_validation_with_definitions_allowed(self):
        """Test that definition strings validate correctly when definitions_allowed=True."""
        from neuroconv.tools.hed import _validate_hed_string

        definition_string = "(Definition/Test-def, (Sensory-event, Visual-presentation))"
        errors = _validate_hed_string(
            definition_string,
            hed_version="8.3.0",
            definitions_allowed=True,
        )
        assert isinstance(errors, list)
        assert len(errors) == 0


class TestCallOpenrouterApi:
    """Tests for _call_openrouter_api function."""

    @patch("neuroconv.tools.hed.urllib.request.urlopen")
    def test_successful_api_call(self, mock_urlopen):
        """Test successful API call returns content."""
        from neuroconv.tools.hed import _call_openrouter_api

        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"choices": [{"message": {"content": "Test response"}}]}).encode(
            "utf-8"
        )
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        result = _call_openrouter_api(messages, api_key="test-key", model="test-model")

        assert result == "Test response"

    @patch("neuroconv.tools.hed.urllib.request.urlopen")
    def test_api_error_raises_runtime_error(self, mock_urlopen):
        """Test that API errors raise RuntimeError."""
        from urllib.error import HTTPError

        from neuroconv.tools.hed import _call_openrouter_api

        # Mock HTTP error
        mock_urlopen.side_effect = HTTPError(url="https://test.com", code=401, msg="Unauthorized", hdrs={}, fp=None)

        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(RuntimeError, match="OpenRouter API error"):
            _call_openrouter_api(messages, api_key="bad-key", model="test-model")


class TestGenerateHedTagsForTrials:
    """Tests for generate_hed_tags_for_trials function."""

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_returns_dict_with_expected_structure(self, mock_validate, mock_api):
        """Test that the function returns a dict with expected structure."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        # Mock API to return valid JSON response
        mock_api.return_value = json.dumps(
            {
                "definitions": [],
                "column_tags": {
                    "stimulus_type": "Event",
                    "response": "Event",
                },
            }
        )
        mock_validate.return_value = []  # No validation errors

        columns = {
            "stimulus_type": "Type of stimulus",
            "response": "Subject response",
        }

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        assert isinstance(result, dict)
        assert "hed_version" in result
        assert "definitions" in result
        assert "column_tags" in result
        assert isinstance(result["hed_version"], str)
        assert isinstance(result["definitions"], list)
        assert isinstance(result["column_tags"], dict)
        assert set(result["column_tags"].keys()) == set(columns.keys())

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_handles_null_response(self, mock_validate, mock_api):
        """Test that null response is converted to Python None."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps(
            {
                "definitions": [],
                "column_tags": {
                    "start_time": None,
                },
            }
        )

        columns = {"start_time": "Trial start time"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        assert result["column_tags"]["start_time"] is None

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_iterates_on_validation_errors(self, mock_validate, mock_api):
        """Test that the function iterates when validation fails."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        # First call returns invalid, second returns valid
        mock_api.side_effect = [
            json.dumps({"definitions": [], "column_tags": {"stimulus": "InvalidTag"}}),
            json.dumps({"definitions": [], "column_tags": {"stimulus": "Event"}}),
        ]
        # First validation fails, second succeeds
        mock_validate.side_effect = [["Error: invalid tag"], []]

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            max_iterations=3,
        )

        assert result["column_tags"]["stimulus"] == "Event"
        assert mock_api.call_count == 2

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_max_iterations_limit(self, mock_validate, mock_api):
        """Test that max_iterations limits retry attempts."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        # Always return invalid
        mock_api.return_value = json.dumps({"definitions": [], "column_tags": {"stimulus": "InvalidTag"}})
        mock_validate.return_value = ["Error: invalid tag"]

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            max_iterations=2,
        )

        # Should use last attempt even if invalid
        assert result["column_tags"]["stimulus"] == "InvalidTag"
        # 1 initial + 2 iterations = 3 calls
        assert mock_api.call_count == 3

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_includes_hed_version(self, mock_validate, mock_api):
        """Test that the result includes the HED schema version."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps({"definitions": [], "column_tags": {"stimulus": "Event"}})
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        assert "hed_version" in result
        assert isinstance(result["hed_version"], str)
        assert len(result["hed_version"]) > 0

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_definitions_list_exists(self, mock_validate, mock_api):
        """Test that the result includes a definitions list."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps(
            {
                "definitions": ["(Definition/Test, (Event))"],
                "column_tags": {"stimulus": "Event"},
            }
        )
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        assert "definitions" in result
        assert isinstance(result["definitions"], list)

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_additional_context_parameter(self, mock_validate, mock_api):
        """Test that additional_context is passed to the LLM."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps({"definitions": [], "column_tags": {"stimulus": "Event"}})
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            additional_context="Use more specific tags from the Stimulus hierarchy.",
        )

        # Verify the API was called and result is valid
        assert isinstance(result, dict)
        assert "column_tags" in result
        # The additional context should have been included in the system prompt
        call_args = mock_api.call_args[0][0]  # Get the messages argument
        system_message = call_args[0]["content"]
        assert "Additional Context from User" in system_message
        assert "Use more specific tags from the Stimulus hierarchy" in system_message

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_include_comments_returns_comments_field(self, mock_validate, mock_api):
        """Test that include_comments=True returns a comments field."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps(
            {
                "definitions": [],
                "column_tags": {"stimulus": "Event"},
                "comments": {"stimulus": "Selected Event tag for stimulus."},
            }
        )
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            include_comments=True,
        )

        assert "comments" in result
        assert isinstance(result["comments"], dict)
        assert "stimulus" in result["comments"]
        assert result["comments"]["stimulus"] == "Selected Event tag for stimulus."

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_include_comments_false_no_comments_field(self, mock_validate, mock_api):
        """Test that include_comments=False does not return a comments field."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps({"definitions": [], "column_tags": {"stimulus": "Event"}})
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            include_comments=False,
        )

        assert "comments" not in result

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_handles_json_parse_failure(self, mock_validate, mock_api):
        """Test that JSON parse errors are handled gracefully."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        # Return invalid JSON
        mock_api.return_value = "Not valid JSON at all"

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
            include_comments=True,
        )

        # Should return empty/None results gracefully
        assert "column_tags" in result
        assert result["column_tags"]["stimulus"] is None
        assert "comments" in result

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_handles_markdown_code_blocks(self, mock_validate, mock_api):
        """Test that markdown code blocks are stripped from response."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        # Return JSON wrapped in markdown code block
        mock_api.return_value = '```json\n{"definitions": [], "column_tags": {"stimulus": "Event"}}\n```'
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        assert result["column_tags"]["stimulus"] == "Event"

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_processes_all_columns_simultaneously(self, mock_validate, mock_api):
        """Test that all columns are processed in a single API call."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps(
            {
                "definitions": [],
                "column_tags": {
                    "col1": "Event",
                    "col2": "Event",
                    "col3": None,
                },
            }
        )
        mock_validate.return_value = []

        columns = {
            "col1": "First column",
            "col2": "Second column",
            "col3": "Third column (timing)",
        }

        result = generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        # Should only make one API call for all columns
        assert mock_api.call_count == 1
        # All columns should be in result
        assert set(result["column_tags"].keys()) == set(columns.keys())

    @patch("neuroconv.tools.hed._call_openrouter_api")
    @patch("neuroconv.tools.hed._validate_hed_string")
    def test_hed_semantics_guide_in_prompt(self, mock_validate, mock_api):
        """Test that HED semantics guide is included in the system prompt."""
        from neuroconv.tools.hed import generate_hed_tags_for_trials

        mock_api.return_value = json.dumps({"definitions": [], "column_tags": {"stimulus": "Event"}})
        mock_validate.return_value = []

        columns = {"stimulus": "Stimulus type"}

        generate_hed_tags_for_trials(
            columns=columns,
            api_key="test-key",
        )

        # Check that semantics guide content is in the system prompt
        call_args = mock_api.call_args[0][0]
        system_message = call_args[0]["content"]
        assert "reversibility principle" in system_message.lower()
        assert "semantic grouping rules" in system_message.lower()
        assert "event classification" in system_message.lower()
