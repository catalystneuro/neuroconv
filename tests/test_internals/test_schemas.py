from jsonschema import Draft7Validator
from pathlib import Path

import pytest

from neuroconv.datainterfaces.interface_list import interface_list
from neuroconv.utils import load_dict_from_file


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_source_schema(data_interface):
    schema = data_interface.get_source_schema()
    Draft7Validator.check_schema(schema=schema)


@pytest.mark.parametrize("data_interface", interface_list)
def test_interface_conversion_options_schema(data_interface):
    schema = data_interface.get_conversion_options_schema()
    Draft7Validator.check_schema(schema=schema)


def test_yaml_specification_schema():
    schema = load_dict_from_file(
        file_path=Path(__file__).parent.parent.parent
        / "src"
        / "neuroconv"
        / "schemas"
        / "yaml_conversion_specification_schema.json"
    )
    Draft7Validator.check_schema(schema=schema)
