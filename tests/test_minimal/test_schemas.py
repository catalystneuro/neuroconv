from pathlib import Path

from jsonschema import Draft7Validator

from neuroconv.utils import load_dict_from_file


def test_yaml_specification_schema():
    schema = load_dict_from_file(
        file_path=Path(__file__).parent.parent.parent
        / "src"
        / "neuroconv"
        / "schemas"
        / "yaml_conversion_specification_schema.json"
    )
    Draft7Validator.check_schema(schema=schema)
