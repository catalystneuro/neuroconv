from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

import pytest
from jsonschema import validate
from pydantic import DirectoryPath, FilePath
from pynwb import NWBFile

from neuroconv.datainterfaces import AlphaOmegaRecordingInterface
from neuroconv.utils import ArrayType, DeepDict, get_json_schema_from_method_signature


def test_get_json_schema_from_method_signature_basic():
    def basic_method(
        integer: int,
        floating: float,
        string_or_path: Union[Path, str],
        boolean: bool,
        literal: Literal["a", "b", "c"],
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
            "literal": {"enum": ["a", "b", "c"], "type": "string"},
            "optional_dictionary": {
                "anyOf": [{"additionalProperties": {"type": "string"}, "type": "object"}, {"type": "null"}],
                "default": None,
            },
            "string_or_path": {"anyOf": [{"format": "path", "type": "string"}, {"type": "string"}]},
            "string_with_default": {"default": "hi", "type": "string"},
        },
        "required": ["integer", "floating", "string_or_path", "boolean", "literal", "dictionary"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_advanced():
    """
    These are annotations newly supported by the Pydantic-based inference.

    They should also be compatible with __future__.annotations for SpikeInterface.
    """

    # TODO: enable | instead of union when 3.11 is minimal
    def advanced_method(
        old_list_of_strings: List[str],
        new_list_of_strings: list[str],
        old_dict_of_ints: Dict[str, int],
        new_dict_of_ints: dict[str, int],
        nested_list_of_strings: List[List[str]],
        array_type: ArrayType,
        # more_nested_list_of_strings: list[list[list[str]]],
        # pathalogical_case: list[dict[str | int | None, list[Optional[dict[str, list[Literal["a", "b"] | None]]]]],],
    ):
        pass

    test_json_schema = get_json_schema_from_method_signature(method=advanced_method)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "array_type": {"items": {}, "type": "array"},
            "nested_list_of_strings": {"items": {"items": {"type": "string"}, "type": "array"}, "type": "array"},
            "new_dict_of_ints": {"additionalProperties": {"type": "integer"}, "type": "object"},
            "new_list_of_strings": {"items": {"type": "string"}, "type": "array"},
            "old_dict_of_ints": {"additionalProperties": {"type": "integer"}, "type": "object"},
            "old_list_of_strings": {"items": {"type": "string"}, "type": "array"},
        },
        "required": [
            "old_list_of_strings",
            "new_list_of_strings",
            "old_dict_of_ints",
            "new_dict_of_ints",
            "nested_list_of_strings",
            "array_type",
        ],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_exclude():
    def basic_method(
        integer_to_keep: int,
        floating_to_ignore: float,
    ):
        pass

    test_exclude = ["string_with_default", "floating"]
    test_json_schema = get_json_schema_from_method_signature(method=basic_method, exclude=test_exclude)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {"floating_to_ignore": {"type": "number"}, "integer_to_keep": {"type": "integer"}},
        "required": ["integer_to_keep", "floating_to_ignore"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_init():
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


def test_get_json_schema_from_method_signature_class_static():
    """Ensuring that signature assembly prior to passing to Pydantic is not affected by bound or static methods."""

    class TestClass:

        @staticmethod
        def test_static_method(integer: int, string: str, boolean: bool):
            pass

    test_json_schema = get_json_schema_from_method_signature(method=TestClass.test_static_method)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "integer": {"type": "integer"},
            "string": {"type": "string"},
        },
        "required": ["integer", "string", "boolean"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_class_method():
    """Test that 'cls' is automatically skipped."""

    class TestClass:

        @classmethod
        def some_class_method(cls, integer: int, string: str, boolean: bool):
            pass

    test_json_schema = get_json_schema_from_method_signature(method=TestClass.some_class_method)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {
            "boolean": {"type": "boolean"},
            "integer": {"type": "integer"},
            "string": {"type": "string"},
        },
        "required": ["integer", "string", "boolean"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_with_kwargs():
    def method_with_kwargs(integer: int, **kwargs):
        pass

    test_json_schema = get_json_schema_from_method_signature(method=method_with_kwargs)
    expected_json_schema = {
        "additionalProperties": True,
        "properties": {"integer": {"type": "integer"}},
        "required": ["integer"],
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
            "verbose": {"default": False, "type": "boolean", "description": "Allows verbose.\nDefault is False."},
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


def test_get_json_schema_from_method_signature_simple_docstring():
    def method_with_docstring(integer: int):
        """
        This is a simple docstring.

        Parameters
        ----------
        integer : int
            This is an integer.
        """
        pass

    test_json_schema = get_json_schema_from_method_signature(method=method_with_docstring)
    expected_json_schema = {
        "additionalProperties": False,
        "properties": {"integer": {"description": "This is an integer.", "type": "integer"}},
        "required": ["integer"],
        "type": "object",
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_docstring_warning():
    def method_with_typo_in_docstring(integer: int):
        """
        This is a docstring with a typo in the argument name.

        Parameters
        ----------
        integ : int
            This is an integer.
        """
        pass

    with pytest.warns(expected_warning=UserWarning) as warning_info:
        test_json_schema = get_json_schema_from_method_signature(method=method_with_typo_in_docstring)

    assert len(warning_info) == 1

    expected_warning_message = (
        "The argument_name 'integ' from the docstring of method 'method_with_typo_in_docstring' does not occur in "
        "the signature, possibly due to a typo."
    )
    assert warning_info[0].message.args[0] == expected_warning_message

    expected_json_schema = {
        "properties": {"integer": {"type": "integer"}},
        "required": ["integer"],
        "type": "object",
        "additionalProperties": False,
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_docstring_warning_with_exclusions():
    def method_with_typo_in_docstring_and_exclusions(integer: int, nwbfile: NWBFile, metadata: DeepDict):
        """
        This is a docstring with a typo in the argument name.

        Parameters
        ----------
        integ : int
            This is an integer.
        nwbfile : pynwb.NWBFile
            An in-memory NWBFile object.
        metadata : neuroconv.utils.DeepDict
            A dictionary-like object that allows for deep access and modification.
        """
        pass

    with pytest.warns(expected_warning=UserWarning) as warning_info:
        test_json_schema = get_json_schema_from_method_signature(
            method=method_with_typo_in_docstring_and_exclusions, exclude=["nwbfile", "metadata"]
        )

    assert len(warning_info) == 1

    expected_warning_message = (
        "The argument_name 'integ' from the docstring of method 'method_with_typo_in_docstring_and_exclusions' "
        "does not occur in the signature, possibly due to a typo."
    )
    assert warning_info[0].message.args[0] == expected_warning_message

    expected_json_schema = {
        "properties": {"integer": {"type": "integer"}},
        "required": ["integer"],
        "type": "object",
        "additionalProperties": False,
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_docstring_warning_from_bound_method():
    class TestClass:
        def test_bound_method(self, integer: int):
            """
            This is a docstring with a typo in the argument name.

            Parameters
            ----------
            integ : int
                This is an integer.
            """
            pass

    with pytest.warns(expected_warning=UserWarning) as warning_info:
        test_json_schema = get_json_schema_from_method_signature(method=TestClass.test_bound_method)

    assert len(warning_info) == 1

    expected_warning_message = (
        "The argument_name 'integ' from the docstring of method 'TestClass.test_bound_method' does not occur in the "
        "signature, possibly due to a typo."
    )
    assert warning_info[0].message.args[0] == expected_warning_message

    expected_json_schema = {
        "properties": {"integer": {"type": "integer"}},
        "required": ["integer"],
        "type": "object",
        "additionalProperties": False,
    }

    assert test_json_schema == expected_json_schema


def test_get_json_schema_from_method_signature_docstring_warning_from_class_method():
    class TestClass:
        @classmethod
        def test_class_method(self, integer: int):
            """
            This is a docstring with a typo in the argument name.

            Parameters
            ----------
            integ : int
                This is an integer.
            """
            pass

    with pytest.warns(expected_warning=UserWarning) as warning_info:
        test_json_schema = get_json_schema_from_method_signature(method=TestClass.test_class_method)

    assert len(warning_info) == 1

    expected_warning_message = (
        "The argument_name 'integ' from the docstring of method 'TestClass.test_class_method' does not occur in the "
        "signature, possibly due to a typo."
    )
    assert warning_info[0].message.args[0] == expected_warning_message

    expected_json_schema = {
        "properties": {"integer": {"type": "integer"}},
        "required": ["integer"],
        "type": "object",
        "additionalProperties": False,
    }

    assert test_json_schema == expected_json_schema


def test_json_schema_raises_error_for_missing_type_annotations():
    """Test that attempting to generate a JSON schema for a method with missing type annotations raises a TypeError."""
    # https://github.com/catalystneuro/neuroconv/pull/1157

    def test_method(param_with_type: int, param_without_type, param_with_default="default_value"):
        pass

    with pytest.raises(
        TypeError,
        match=(
            "Parameter 'param_without_type' in method 'test_method' is missing a type annotation. "
            "Either add a type annotation for 'param_without_type' or add it to the exclude list."
        ),
    ):
        get_json_schema_from_method_signature(method=test_method)
