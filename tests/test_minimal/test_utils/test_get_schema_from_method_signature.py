from pathlib import Path
from typing import Dict, Optional, Union

from jsonschema import validate
from pydantic import DirectoryPath, FilePath

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

    test_json_schema = get_json_schema_from_method_signature(method=basic_method)
    expected_json_schema = {
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

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_exclude():
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

    test_exclude = ["string_with_default", "floating"]
    test_json_schema = get_json_schema_from_method_signature(method=basic_method, exclude=test_exclude)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "dictionary": {"additionalProperties": {"type": "string"}, "type": "object"},
            "integer": {"type": "integer"},
            "optional_dictionary": {
                "anyOf": [{"additionalProperties": {"type": "string"}, "type": "object"}, {"type": "null"}],
                "default": None,
            },
            "string_or_path": {"anyOf": [{"format": "path", "type": "string"}, {"type": "string"}]},
        },
        "required": ["integer", "string_or_path", "boolean", "dictionary"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_schema_from_method_signature_init():
    """Test that 'self' is automatically skipped."""

    class TestClass:
        def __init__(
            self,
            file_path: FilePath,
            folder_path: DirectoryPath,
            old_annotation_1: str,
            old_annotation_2: Path,
            old_annotation_3: Union[str, Path],
        ):
            pass

    test_json_schema = get_json_schema_from_method_signature(method=TestClass.__init__)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "file_path": {"format": "file-path", "type": "string"},
            "folder_path": {"format": "directory-path", "type": "string"},
            "old_annotation_1": {"type": "string"},
            "old_annotation_2": {"format": "path", "type": "string"},
            "old_annotation_3": {"anyOf": [{"type": "string"}, {"format": "path", "type": "string"}]},
        },
        "required": ["file_path", "folder_path", "old_annotation_1", "old_annotation_2", "old_annotation_3"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_schema_from_method_signature_class_static():
    """Ensuring that signature assembly prior to passing to Pydantic is not affected by bound or static methods."""

    class TestClass:

        @staticmethod
        def test_static_method(integer: int, string: str, boolean: bool, number: float):
            pass

    test_json_schema = get_json_schema_from_method_signature(method=TestClass.test_static_method)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "integer": {"type": "integer"},
            "number": {"type": "number"},
            "string": {"type": "string"},
        },
        "required": ["integer", "string", "boolean", "number"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_schema_from_method_signature_class_method():
    """Test that 'cls' is automatically skipped."""

    class TestClass:

        @classmethod
        def some_class_method(cls, integer: int, string: str, boolean: bool, number: float):
            pass

    test_json_schema = get_json_schema_from_method_signature(method=TestClass.some_class_method)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "integer": {"type": "integer"},
            "number": {"type": "number"},
            "string": {"type": "string"},
        },
        "required": ["integer", "string", "boolean", "number"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_example_data_interface():
    test_json_schema = get_json_schema_from_method_signature(AlphaOmegaRecordingInterface.__init__)
    expected_json_schema = {
        "properties": {
            "folder_path": {
                "format": "directory-path",
                "type": "string",
                "description": "Path to the folder of .mpx files.",
            },
            "verbose": {"default": True, "type": "boolean", "description": "Allows verbose.\nDefault is True."},
            "es_key": {"default": "ElectricalSeries", "type": "string"},
        },
        "required": ["folder_path"],
        "type": "object",
        "additionalProperties": False,
    }

    assert test_json_schema == expected_json_schema


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

    test_conversion_options_schema = get_json_schema_from_method_signature(method=Test358.add_to_nwbfile)
    expected_conversion_options_schema = {
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

    assert test_conversion_options_schema == expected_conversion_options_schema

    # Validation used to fail due to lack of Dict[str, str] support
    test_conversion_options = dict(column_name_mapping=dict(condition="cond"))
    validate(instance=test_conversion_options, schema=test_conversion_options_schema)
