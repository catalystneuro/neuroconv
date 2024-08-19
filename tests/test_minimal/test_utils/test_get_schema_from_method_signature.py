from pathlib import Path
from typing import Dict, Optional, Union

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
        "additionalProperties": False,
        "properties": {
            "es_key": {"default": "ElectricalSeries", "type": "string"},
            "folder_path": {
                "anyOf": [{"type": "string"}, {"format": "path", "type": "string"}],
                "description": "Path to the folder of .mpx " "files.",
            },
            "verbose": {"default": True, "description": "Allows verbose.\nDefault is True.", "type": "boolean"},
        },
        "required": ["folder_path"],
        "type": "object",
    }
