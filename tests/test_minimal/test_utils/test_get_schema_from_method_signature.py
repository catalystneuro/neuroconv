from pathlib import Path
from typing import Dict, Optional, Union

from jsonschema import validate

from neuroconv.datainterfaces import AlphaOmegaRecordingInterface
from neuroconv.utils import get_json_schema_from_method_signature


def test_get_json_schema_from_method_signature_basic():
    def basic_method(
        integer: int,
        floating: float,
        string_or_path: Union[Path, str],
        boolean: bool,
        dictionary: Dict[str, str],
        string_with_default: str = "hi",
        optional_dictionary: Optional[Dict[str, str]] = None,
    ):
        pass

    json_schema = get_json_schema_from_method_signature(method=basic_method)

    assert json_schema == {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "dictionary": {"additionalProperties": {"type": "string"}, "type": "object"},
            "floating": {"type": "number"},
            "integer": {"type": "integer"},
            "optional_dictionary": {
                "anyOf": [{"additionalProperties": {"type": "string"}, "type": "object"}, {"type": "null"}],
                "default": None,
            },
            "string_or_path": {"anyOf": [{"format": "path", "type": "string"}, {"type": "string"}]},
            "string_with_default": {"default": "hi", "type": "string"},
        },
        "required": ["integer", "floating", "string_or_path", "boolean", "dictionary"],
        "type": "object",
    }


# def test_get_schema_from_method_signature_exclude():
#     def test1():
#         pass
#
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}
#
#
# def test_get_schema_from_method_signature_init():
#     class SomeInterface:
#         def __init__(self, file_path: FilePath, folder_path: DirectoryPath, old_annotation_1: str, old_annotation_2: pathlib.Path, old_annotation_3: Union[str, pathlib.Path]):
#             pass
#
#     json_schema = get_schema_from_method_signature(method=SomeInterface.__init__)
#
#     assert json_schema == {}
#
# def test_get_schema_from_method_signature_class_static():
#     class SomeInterface:
#
#         @staticmethod
#         def some_static_method(integer: int, string: str, boolean: bool, number: float):
#             pass
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}
#
# def test_get_schema_from_method_signature_class_method():
#     class SomeInterface:
#
#         @classmethod
#         def some_static_method(cls, integer: int, string: str, boolean: bool, number: float):
#             pass
#
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}

# def test_get_json_schema_from_method_signature_previous_1():
#     class A:
#         def __init__(self, a: int, b: float, c: Union[Path, str], d: bool, e: str = "hi", f: Dict[str, str] = None):
#             pass
#
#     schema = get_schema_from_method_signature(A.__init__)
#
#     correct_schema = dict(
#         additionalProperties=False,
#         properties=dict(
#             a=dict(type="number"),
#             b=dict(type="number"),
#             c=dict(type="string"),
#             d=dict(type="boolean"),
#             e=dict(default="hi", type="string"),
#             f=dict(type="object", additionalProperties={"^.*$": dict(type="string")}),
#         ),
#         required=[
#             "a",
#             "b",
#             "c",
#             "d",
#         ],
#         type="object",
#     )
#
#     assert schema == correct_schema


def test_get_schema_from_example_data_interface():
    schema = get_json_schema_from_method_signature(AlphaOmegaRecordingInterface.__init__)

    assert schema == {
        "required": ["folder_path"],
        "properties": {
            "folder_path": {
                "format": "directory",
                "description": "Path to the folder of .mpx files.",
                "type": "string",
            },
            "verbose": {"description": "Allows verbose.\nDefault is True.", "type": "boolean", "default": True},
            "es_key": {"type": "string", "default": "ElectricalSeries"},
        },
        "type": "object",
        "additionalProperties": False,
    }
    assert schema == {
        "properties": {
            "folder_path": {
                "anyOf": [{"type": "string"}, {"format": "path", "type": "string"}],
                "description": "Path to the folder of .mpx files.",
            },
            "verbose": {"default": True, "type": "boolean", "description": "Allows verbose.\nDefault is True."},
            "es_key": {"default": "ElectricalSeries", "type": "string"},
        },
        "required": ["folder_path"],
        "type": "object",
        "additionalProperties": False,
    }


def test_fix_to_358():
    """Testing a fix to problem in https://github.com/catalystneuro/neuroconv/issues/358."""

    class Test358:
        def add_to_nwbfile(
            self,
            metadata: Optional[dict] = None,
            tag: str = "trials",
            column_name_mapping: Optional[Dict[str, str]] = None,
            column_descriptions: Optional[Dict[str, str]] = None,
        ):
            pass

    conversion_options_schema = get_json_schema_from_method_signature(method=Test358.add_to_nwbfile)
    assert conversion_options_schema == {
        "properties": {
            "metadata": {"anyOf": [{"type": "object"}, {"type": "null"}], "default": None},
            "tag": {"default": "trials", "type": "string"},
            "column_name_mapping": {
                "anyOf": [{"additionalProperties": {"type": "string"}, "type": "object"}, {"type": "null"}],
                "default": None,
            },
            "column_descriptions": {
                "anyOf": [{"additionalProperties": {"type": "string"}, "type": "object"}, {"type": "null"}],
                "default": None,
            },
        },
        "type": "object",
        "additionalProperties": False,
    }

    # Validation used to fail due to lack of Dict[str, str] support
    conversion_options = dict(column_name_mapping=dict(condition="cond"))
    validate(instance=conversion_options, schema=conversion_options_schema)
