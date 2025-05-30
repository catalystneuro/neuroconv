import collections.abc
import inspect
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Type

import docstring_parser
import hdmf.data_utils
import numpy as np
import pydantic
import pynwb
from jsonschema import validate
from pynwb.device import Device
from pynwb.icephys import IntracellularElectrode


class _GenericNeuroconvEncoder(json.JSONEncoder):
    """Generic JSON encoder for NeuroConv data."""

    def default(self, obj):
        """
        Serialize custom data types to JSON. This overwrites the default method of the JSONEncoder class.
        """
        # Over-write behaviors for datetime object
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Transform numpy generic integers and floats to python ints floats
        if isinstance(obj, np.generic):
            return obj.item()

        # Numpy arrays should be converted to lists
        if isinstance(obj, np.ndarray):
            return obj.tolist()

        # Over-write behaviors for Paths
        if isinstance(obj, Path):
            return str(obj)

        # The base-class handles it
        return super().default(obj)


class _NWBMetaDataEncoder(_GenericNeuroconvEncoder):
    """
    Custom JSON encoder for NWB metadata.
    """


class _NWBSourceDataEncoder(_GenericNeuroconvEncoder):
    """
    Custom JSON encoder for data interface source data (i.e. kwargs).
    """


class _NWBConversionOptionsEncoder(_GenericNeuroconvEncoder):
    """
    Custom JSON encoder for conversion options of the data interfaces and converters (i.e. kwargs).
    """


# This is used in the Guide so we will keep it public.
NWBMetaDataEncoder = _NWBMetaDataEncoder


def get_base_schema(
    tag: str | None = None,
    root: bool = False,
    id_: str | None = None,
    required: list[str] | None = None,
    properties: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Return the base schema used for all other schemas.

    Parameters
    ----------
    tag : str, optional
        Tag to identify the schema.
    root : bool, default: False
        Whether this schema is a root schema.
    id_ : str, optional
        Schema identifier.
    required : list of str, optional
        List of required property names.
    properties : dict, optional
        Dictionary of property definitions.
    **kwargs
        Additional schema properties.

    Returns
    -------
    dict
        Base JSON schema with the following structure:
        {
            "required": List of required properties (empty if not provided)
            "properties": Dictionary of property definitions (empty if not provided)
            "type": "object"
            "additionalProperties": False
            "tag": Optional tag if provided
            "$schema": Schema version if root is True
            "$id": Schema ID if provided
            **kwargs: Any additional properties
        }
    """
    base_schema = dict(
        required=required or [],
        properties=properties or {},
        type="object",
        additionalProperties=False,
    )
    if tag is not None:
        base_schema.update(tag=tag)
    if root:
        base_schema.update({"$schema": "http://json-schema.org/draft-07/schema#"})
    if id_ is not None:
        base_schema.update({"$id": id_})
    base_schema.update(**kwargs)
    return base_schema


def get_json_schema_from_method_signature(method: Callable, exclude: list[str] | None = None) -> dict[str, Any]:
    """
    Get the equivalent JSON schema for a signature of a method.

    Also uses `docstring_parser` (NumPy style) to attempt to find descriptions for the arguments.

    Parameters
    ----------
    method : callable
        The method to generate the JSON schema from.
    exclude : list of str, optional
        List of arguments to exclude from the schema generation.
        Always includes 'self' and 'cls'.

    Returns
    -------
    json_schema : dict
        The JSON schema corresponding to the method signature.
    """
    exclude = exclude or []
    exclude += ["self", "cls"]

    split_qualname = method.__qualname__.split(".")[-2:]
    method_display = ".".join(split_qualname) if "<" not in split_qualname[0] else method.__name__

    signature = inspect.signature(obj=method)
    parameters = signature.parameters
    additional_properties = False
    arguments_to_annotations = {}
    for argument_name in parameters:
        if argument_name in exclude:
            continue

        parameter = parameters[argument_name]

        if parameter.kind == inspect.Parameter.VAR_KEYWORD:  # Skip all **{...} usage
            additional_properties = True
            continue

        # Raise error if the type annotation is missing as a json schema cannot be generated in that case
        if parameter.annotation is inspect._empty:
            raise TypeError(
                f"Parameter '{argument_name}' in method '{method_display}' is missing a type annotation. "
                f"Either add a type annotation for '{argument_name}' or add it to the exclude list."
            )

        # Pydantic uses ellipsis for required
        pydantic_default = ... if parameter.default is inspect._empty else parameter.default
        arguments_to_annotations.update({argument_name: (parameter.annotation, pydantic_default)})

    # The ConfigDict is required to support custom types like NumPy arrays
    model = pydantic.create_model(
        "_TempModel", __config__=pydantic.ConfigDict(arbitrary_types_allowed=True), **arguments_to_annotations
    )

    temp_json_schema = model.model_json_schema()

    # We never used to include titles in the lower schema layers
    # But Pydantic does automatically
    json_schema = _copy_without_title_keys(temp_json_schema)

    # Pydantic does not make determinations on additionalProperties
    json_schema["additionalProperties"] = additional_properties

    # Attempt to find descriptions within the docstring of the method
    parsed_docstring = docstring_parser.parse(method.__doc__)
    for parameter_in_docstring in parsed_docstring.params:
        if parameter_in_docstring.arg_name in exclude:
            continue

        if parameter_in_docstring.arg_name not in json_schema["properties"]:
            message = (
                f"The argument_name '{parameter_in_docstring.arg_name}' from the docstring of method "
                f"'{method_display}' does not occur in the signature, possibly due to a typo."
            )
            warnings.warn(message=message, stacklevel=2)
            continue

        if parameter_in_docstring.description is not None:
            json_schema["properties"][parameter_in_docstring.arg_name].update(
                description=parameter_in_docstring.description
            )
    # TODO: could also add Field support for more direct control over docstrings (and enhanced validation conditions)

    return json_schema


def _copy_without_title_keys(d: Any) -> dict[str, Any] | None:
    if not isinstance(d, dict):
        return d

    return {key: _copy_without_title_keys(value) for key, value in d.items() if key != "title"}


def fill_defaults(schema: dict[str, Any], defaults: dict[str, Any], overwrite: bool = True) -> None:
    """
    Insert the values of the defaults dict as default values in the schema in place.

    Parameters
    ----------
    schema: dict
    defaults: dict
    overwrite: bool
    """
    # patternProperties introduced with the CsvTimeIntervalsInterface
    # caused issue with NWBConverter.get_metadata_schema() call leading here
    properties_reference = "properties"
    if properties_reference not in schema and "patternProperties" in schema:
        properties_reference = "patternProperties"

    for key, val in schema[properties_reference].items():
        if key in defaults:
            if val["type"] == "object":
                fill_defaults(val, defaults[key], overwrite=overwrite)
            else:
                if overwrite or ("default" not in val):
                    val["default"] = defaults[key]


def unroot_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Modify a json-schema dictionary to make it not root.

    Parameters
    ----------
    schema: dict
    """
    terms = ("required", "properties", "type", "additionalProperties", "title", "description")
    return {k: v for k, v in schema.items() if k in terms}


def _is_member(types: Type | tuple[Type, ...], target_types: Type | tuple[Type, ...]) -> bool:
    if not isinstance(target_types, tuple):
        target_types = (target_types,)
    if not isinstance(types, tuple):
        types = (types,)
    return any(t in target_types for t in types)


def get_schema_from_hdmf_class(hdmf_class: Type) -> dict[str, Any]:
    """
    Get metadata schema from hdmf class.

    Parameters
    ----------
    hdmf_class : type
        The HDMF class to generate a schema from.

    Returns
    -------
    dict
        JSON schema derived from the HDMF class, containing:
        - tag: Full class path (module.name)
        - required: List of required fields
        - properties: Dictionary of field definitions including types and descriptions
        - additionalProperties: Whether extra fields are allowed
    """
    schema = get_base_schema()
    schema["tag"] = hdmf_class.__module__ + "." + hdmf_class.__name__

    # Detect child-like (as opposed to link) fields
    pynwb_children_fields = [f["name"] for f in hdmf_class.get_fields_conf() if f.get("child", False)]
    # For MultiContainerInterface
    if hasattr(hdmf_class, "__clsconf__"):
        pynwb_children_fields.append(hdmf_class.__clsconf__["attr"])
    # Temporary solution before this is solved: https://github.com/hdmf-dev/hdmf/issues/475
    if "device" in pynwb_children_fields:
        pynwb_children_fields.remove("device")

    docval = hdmf_class.__init__.__docval__
    for docval_arg in docval["args"]:
        arg_name = docval_arg["name"]
        arg_type = docval_arg["type"]

        schema_val = dict(description=docval_arg["doc"])

        if arg_name == "name":
            schema_val.update(pattern="^[^/]*$")

        if _is_member(arg_type, (float, int, "float", "int")):
            schema_val.update(type="number")
        elif _is_member(arg_type, str):
            schema_val.update(type="string")
        elif _is_member(arg_type, collections.abc.Iterable):
            schema_val.update(type="array")
        elif isinstance(arg_type, tuple) and (np.ndarray in arg_type and hdmf.data_utils.DataIO not in arg_type):
            # extend type array without including type where DataIO in tuple
            schema_val.update(type="array")
        elif _is_member(arg_type, datetime):
            schema_val.update(type="string", format="date-time")
        elif _is_member(arg_type, (pynwb.base.TimeSeries, pynwb.ophys.PlaneSegmentation)):
            continue
        else:
            if not isinstance(arg_type, tuple):
                docval_arg_type = [arg_type]
            else:
                docval_arg_type = arg_type
            # if another nwb object (or list of nwb objects)
            if any([hasattr(t, "__nwbfields__") for t in docval_arg_type]):
                is_nwb = [hasattr(t, "__nwbfields__") for t in docval_arg_type]
                item = docval_arg_type[np.where(is_nwb)[0][0]]
                # if it is child
                if arg_name in pynwb_children_fields:
                    items = get_schema_from_hdmf_class(item)
                    schema_val.update(type="array", items=items, minItems=1, maxItems=1)
                # if it is a link
                else:
                    target = item.__module__ + "." + item.__name__
                    schema_val.update(type="string", target=target)
            else:
                continue
        # Check for default arguments
        if "default" in docval_arg:
            if docval_arg["default"] is not None:
                schema_val.update(default=docval_arg["default"])
        else:
            schema["required"].append(arg_name)
        schema["properties"][arg_name] = schema_val
    if "allow_extra" in docval:
        schema["additionalProperties"] = docval["allow_extra"]
    return schema


def get_metadata_schema_for_icephys() -> dict[str, Any]:
    """
    Returns the metadata schema for icephys data.

    Returns
    -------
    dict
        The metadata schema for icephys data, containing definitions for Device,
        Electrode, and Session configurations.
    """
    schema = get_base_schema(tag="Icephys")
    schema["required"] = ["Device", "Electrodes"]
    schema["properties"] = dict(
        Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Icephys/definitions/Device"}),
        Electrodes=dict(
            type="array",
            minItems=1,
            items={"$ref": "#/properties/Icephys/definitions/Electrode"},
        ),
        Sessions=dict(
            type="array",
            minItems=1,
            items={"$ref": "#/properties/Icephys/definitions/Sessions"},
        ),
    )

    schema["definitions"] = dict(
        Device=get_schema_from_hdmf_class(Device),
        Electrode=get_schema_from_hdmf_class(IntracellularElectrode),
        Sessions=dict(
            name={"type": "string", "description": "Session name."},
            relative_session_start_time={
                "type": "number",
                "description": "the start time of the sessions in seconds, relative to the absolute start time",
            },
            icephys_experiment_type={
                "type": "string",
                "description": "Icephys experiment type. Allowed types are: voltage_clamp, current_clamp and izero",
            },
            stimulus_type={
                "type": "string",
                "description": "Description of the type pf stimulus, e.g. Square current clamp.",
            },
            recordings=dict(
                type="array",
                minItems=1,
                items={"$ref": "#/properties/Icephys/definitions/SessionsRecordings"},
            ),
        ),
        SessionsRecordings=dict(
            intracellular_recordings_table_ind={"type": "number", "description": ""},
            simultaneous_recordings_table_ind={"type": "number", "description": ""},
            sequential_recordings_table_ind={"type": "number", "description": ""},
        ),
    )

    return schema


def validate_metadata(metadata: dict[str, dict], schema: dict[str, dict], verbose: bool = False):
    """Validate metadata against a schema."""
    encoder = _NWBMetaDataEncoder()
    # The encoder produces a serialized object, so we deserialized it for comparison

    serialized_metadata = encoder.encode(metadata)
    decoded_metadata = json.loads(serialized_metadata)
    validate(instance=decoded_metadata, schema=schema)
    if verbose:
        print("Metadata is valid!")
