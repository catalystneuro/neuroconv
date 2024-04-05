import collections.abc
import inspect
import json
from datetime import datetime
from typing import Callable, Dict, List, Literal, Optional

import docstring_parser
import hdmf.data_utils
import numpy as np
import pynwb
from jsonschema import validate
from pynwb.device import Device
from pynwb.icephys import IntracellularElectrode

from .dict import dict_deep_update
from .types import FilePathType, FolderPathType


class NWBMetaDataEncoder(json.JSONEncoder):
    def default(self, obj):
        # Over-write behaviors for datetime object
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Transform numpy generic integers and floats to python ints floats
        if isinstance(obj, np.generic):
            return obj.item()

        if isinstance(obj, np.ndarray):
            return obj.tolist()

        # The base-class handles it
        return super().default(obj)


def get_base_schema(
    tag: Optional[str] = None,
    root: bool = False,
    id_: Optional[str] = None,
    required: Optional[List] = None,
    properties: Optional[Dict] = None,
    **kwargs,
) -> dict:
    """Return the base schema used for all other schemas."""
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


def get_schema_from_method_signature(method: Callable, exclude: list = None) -> dict:
    """
    Take a class method and return a json-schema of the input args.

    Parameters
    ----------
    method: function
    exclude: list, optional

    Returns
    -------
    dict

    """
    if exclude is None:
        exclude = ["self", "kwargs"]
    else:
        exclude = exclude + ["self", "kwargs"]
    input_schema = get_base_schema()
    annotation_json_type_map = dict(
        bool="boolean",
        str="string",
        int="number",
        float="number",
        dict="object",
        list="array",
        tuple="array",
        FilePathType="string",
        FolderPathType="string",
    )
    args_spec = dict()
    parsed_docstring = docstring_parser.parse(method.__doc__)
    for param_name, param in inspect.signature(method).parameters.items():
        if param_name in exclude:
            continue
        args_spec[param_name] = dict()
        for doc_param in parsed_docstring.params:
            if doc_param.arg_name == param_name and doc_param.description:
                args_spec[param_name].update(description=doc_param.description)
        if param.annotation:
            if getattr(param.annotation, "__origin__", None) == Literal:
                args_spec[param_name]["enum"] = list(param.annotation.__args__)
            elif getattr(param.annotation, "__origin__", None) == dict:
                args_spec[param_name] = dict(type="object")
                if param.annotation.__args__ == (str, str):
                    args_spec[param_name].update(additionalProperties={"^.*$": dict(type="string")})
                else:
                    args_spec[param_name].update(additionalProperties=True)
            elif hasattr(param.annotation, "__args__"):  # Annotation has __args__ if it was made by typing.Union
                args = param.annotation.__args__
                valid_args = [x.__name__ in annotation_json_type_map for x in args]
                if not any(valid_args):
                    raise ValueError(f"No valid arguments were found in the json type mapping for parameter {param}")
                arg_types = [x for x in np.array(args)[valid_args]]
                param_types = [annotation_json_type_map[x.__name__] for x in arg_types]
                num_params = len(set(param_types))
                conflict_message = (
                    "Conflicting json parameter types were detected from the annotation! "
                    f"{param.annotation.__args__} found."
                )
                # Normally cannot support Union[...] of multiple annotation types
                if num_params > 2:
                    raise ValueError(conflict_message)
                # Special condition for Optional[...]
                if num_params == 2 and not args[1] is type(None):  # noqa: E721
                    raise ValueError(conflict_message)

                # Guaranteed to only have a single index by this point
                args_spec[param_name]["type"] = param_types[0]
                if arg_types[0] == FilePathType:
                    input_schema["properties"].update({param_name: dict(format="file")})
                elif arg_types[0] == FolderPathType:
                    input_schema["properties"].update({param_name: dict(format="directory")})
            else:
                arg = param.annotation
                if arg.__name__ in annotation_json_type_map:
                    args_spec[param_name]["type"] = annotation_json_type_map[arg.__name__]
                else:
                    raise ValueError(
                        f"No valid arguments were found in the json type mapping '{arg}' for parameter {param}"
                    )
                if arg == FilePathType:
                    input_schema["properties"].update({param_name: dict(format="file")})
                if arg == FolderPathType:
                    input_schema["properties"].update({param_name: dict(format="directory")})
        else:
            raise NotImplementedError(
                f"The annotation type of '{param}' in function '{method}' is not implemented! "
                "Please request it to be added at github.com/catalystneuro/nwb-conversion-tools/issues "
                "or create the json-schema for this method manually."
            )
        if param.default is param.empty:
            input_schema["required"].append(param_name)
        elif param.default is not None:
            args_spec[param_name].update(default=param.default)
        input_schema["properties"] = dict_deep_update(input_schema["properties"], args_spec)
        input_schema["additionalProperties"] = param.kind == inspect.Parameter.VAR_KEYWORD
    return input_schema


def fill_defaults(schema: dict, defaults: dict, overwrite: bool = True):
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


def unroot_schema(schema: dict):
    """
    Modify a json-schema dictionary to make it not root.

    Parameters
    ----------
    schema: dict
    """
    terms = ("required", "properties", "type", "additionalProperties", "title", "description")
    return {k: v for k, v in schema.items() if k in terms}


def _is_member(types, target_types):
    if not isinstance(target_types, tuple):
        target_types = (target_types,)
    if not isinstance(types, tuple):
        types = (types,)
    return any(t in target_types for t in types)


def get_schema_from_hdmf_class(hdmf_class):
    """Get metadata schema from hdmf class."""
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


def get_metadata_schema_for_icephys():
    schema = get_base_schema(tag="Icephys")
    schema["required"] = ["Device", "Electrodes"]
    schema["properties"] = dict(
        Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Icephys/properties/definitions/Device"}),
        Electrodes=dict(
            type="array",
            minItems=1,
            items={"$ref": "#/properties/Icephys/properties/definitions/Electrode"},
        ),
        Sessions=dict(
            type="array",
            minItems=1,
            items={"$ref": "#/properties/Icephys/properties/definitions/Sessions"},
        ),
    )

    schema["properties"]["definitions"] = dict(
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
                items={"$ref": "#/properties/Icephys/properties/definitions/SessionsRecordings"},
            ),
        ),
        SessionsRecordings=dict(
            intracellular_recordings_table_ind={"type": "number", "description": ""},
            simultaneous_recordings_table_ind={"type": "number", "description": ""},
            sequential_recordings_table_ind={"type": "number", "description": ""},
        ),
    )

    return schema


def validate_metadata(metadata: Dict[str, dict], schema: Dict[str, dict], verbose: bool = False):
    """Validate metadata against a schema."""
    encoder = NWBMetaDataEncoder()
    # The encoder produces a serialized object, so we deserialized it for comparison

    serialized_metadata = encoder.encode(metadata)
    decoded_metadata = json.loads(serialized_metadata)
    validate(instance=decoded_metadata, schema=schema)
    if verbose:
        print("Metadata is valid!")
