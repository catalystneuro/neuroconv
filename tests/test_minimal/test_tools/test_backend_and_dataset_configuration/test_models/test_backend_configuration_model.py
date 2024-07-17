"""Unit tests for the BackendConfiguration Pydantic model."""

import pytest

from neuroconv.tools.nwb_helpers import BackendConfiguration


def test_model_json_schema_mode_assertion():
    with pytest.raises(AssertionError) as error_info:
        BackendConfiguration.model_json_schema(mode="anything")

    assert "The 'mode' of this method is fixed to be 'validation' and cannot be changed." == str(error_info.value)


def test_model_json_schema_generator_assertion():
    with pytest.raises(AssertionError) as error_info:
        BackendConfiguration.model_json_schema(schema_generator="anything")

    assert "The 'schema_generator' of this method cannot be changed." == str(error_info.value)
