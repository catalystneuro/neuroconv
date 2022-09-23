"""Authors: Luiz Tauffer, Cody Baker, Saksham Sharda and Ben Dichter."""
import collections.abc
import json
import inspect
from datetime import datetime
import numpy as np

import pynwb
from pynwb.device import Device
from pynwb.icephys import IntracellularElectrode

from .dict import dict_deep_update
from .types import FilePathType, FolderPathType


class NWBMetaDataEncoder(json.JSONEncoder):
    def default(self, o):
        # Over-write behaviors for datetime object
        if isinstance(o, datetime):
            return o.isoformat()

        # This should transforms numpy generic integers and floats to python floats
        if isinstance(o, np.generic):
            return o.item()

        # The base-class handles it
        return super().default(o)


def get_base_schema(tag=None, root=False, id_=None, **kwargs) -> dict:
    """Return the base schema used for all other schemas."""
    base_schema = dict(required=[], properties={}, type="object", additionalProperties=False)
    if tag is not None:
        base_schema.update(tag=tag)
    if root:
        base_schema.update({"$schema": "http://json-schema.org/draft-07/schema#"})
    if id_:
        base_schema.update({"$id": id_})
    base_schema.update(**kwargs)
    return base_schema


def get_schema_from_method_signature(class_method: classmethod, exclude: list = None) -> dict:
    """
    Take a class method and return a json-schema of the input args.

    Parameters
    ----------
    class_method: function
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
    for param_name, param in inspect.signature(class_method).parameters.items():
        if param_name not in exclude:
            if param.annotation:
                if hasattr(param.annotation, "__args__"):  # Annotation has __args__ if it was made by typing.Union
                    args = param.annotation.__args__
                    valid_args = [x.__name__ in annotation_json_type_map for x in args]
                    if any(valid_args):
                        param_types = [annotation_json_type_map[x.__name__] for x in np.array(args)[valid_args]]
                    else:
                        raise ValueError("No valid arguments were found in the json type mapping!")
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
                    param_type = param_types[0]
                else:
                    arg = param.annotation
                    if arg.__name__ in annotation_json_type_map:
                        param_type = annotation_json_type_map[arg.__name__]
                    else:
                        raise ValueError(
                            f"No valid arguments were found in the json type mapping {arg} for parameter {param}"
                        )
                    if arg == FilePathType:
                        input_schema["properties"].update({param_name: dict(format="file")})
                    if arg == FolderPathType:
                        input_schema["properties"].update({param_name: dict(format="directory")})
            else:
                raise NotImplementedError(
                    f"The annotation type of '{param}' in function '{class_method}' is not implemented! "
                    "Please request it to be added at github.com/catalystneuro/nwb-conversion-tools/issues "
                    "or create the json-schema for this method manually."
                )
            arg_spec = {param_name: dict(type=param_type)}
            if param.default is param.empty:
                input_schema["required"].append(param_name)
            elif param.default is not None:
                arg_spec[param_name].update(default=param.default)
            input_schema["properties"] = dict_deep_update(input_schema["properties"], arg_spec)
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
    for key, val in schema["properties"].items():
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
        schema_arg = {docval_arg["name"]: dict(description=docval_arg["doc"])}

        # type float
        if docval_arg["type"] == "float" or (
            isinstance(docval_arg["type"], tuple) and any([it in docval_arg["type"] for it in [float, "float"]])
        ):
            schema_arg[docval_arg["name"]].update(type="number")
        # type string
        elif docval_arg["type"] is str or (isinstance(docval_arg["type"], tuple) and str in docval_arg["type"]):
            schema_arg[docval_arg["name"]].update(type="string")
        # type array
        elif docval_arg["type"] is collections.abc.Iterable or (
            isinstance(docval_arg["type"], tuple) and collections.abc.Iterable in docval_arg["type"]
        ):
            schema_arg[docval_arg["name"]].update(type="array")
        # type datetime
        elif docval_arg["type"] is datetime or (
            isinstance(docval_arg["type"], tuple) and datetime in docval_arg["type"]
        ):
            schema_arg[docval_arg["name"]].update(type="string", format="date-time")
        # if TimeSeries, skip it
        elif docval_arg["type"] is pynwb.base.TimeSeries or (
            isinstance(docval_arg["type"], tuple) and pynwb.base.TimeSeries in docval_arg["type"]
        ):
            continue
        # if PlaneSegmentation, skip it
        elif docval_arg["type"] is pynwb.ophys.PlaneSegmentation or (
            isinstance(docval_arg["type"], tuple) and pynwb.ophys.PlaneSegmentation in docval_arg["type"]
        ):
            continue
        else:
            if not isinstance(docval_arg["type"], tuple):
                docval_arg_type = [docval_arg["type"]]
            else:
                docval_arg_type = docval_arg["type"]
            # if another nwb object (or list of nwb objects)
            if any([hasattr(t, "__nwbfields__") for t in docval_arg_type]):
                is_nwb = [hasattr(t, "__nwbfields__") for t in docval_arg_type]
                item = docval_arg_type[np.where(is_nwb)[0][0]]
                # if it is child
                if docval_arg["name"] in pynwb_children_fields:
                    items = get_schema_from_hdmf_class(item)
                    schema_arg[docval_arg["name"]].update(type="array", items=items, minItems=1, maxItems=1)
                # if it is link
                else:
                    target = item.__module__ + "." + item.__name__
                    schema_arg[docval_arg["name"]].update(type="string", target=target)
            else:
                continue
        # Check for default arguments
        if "default" in docval_arg:
            if docval_arg["default"] is not None:
                schema_arg[docval_arg["name"]].update(default=docval_arg["default"])
        else:
            schema["required"].append(docval_arg["name"])
        schema["properties"].update(schema_arg)
    if "allow_extra" in docval:
        schema["additionalProperties"] = docval["allow_extra"]
    return schema


# TODO - centralize into schema folder
def get_schema_for_NWBFile():
    schema = get_base_schema()
    schema["tag"] = "pynwb.file.NWBFile"
    schema["required"] = ["session_description", "identifier", "session_start_time"]
    schema["properties"] = {
        "session_description": {
            "type": "string",
            "format": "long",
            "description": "a description of the session where this data was generated",
        },
        "identifier": {"type": "string", "description": "a unique text identifier for the file"},
        "session_start_time": {
            "type": "string",
            "description": "the start date and time of the recording session",
            "format": "date-time",
        },
        "experimenter": {
            "type": "array",
            "items": {"type": "string", "title": "experimenter"},
            "description": "name of person who performed experiment",
        },
        "experiment_description": {"type": "string", "description": "general description of the experiment"},
        "session_id": {"type": "string", "description": "lab-specific ID for the session"},
        "institution": {"type": "string", "description": "institution(s) where experiment is performed"},
        "notes": {"type": "string", "description": "Notes about the experiment."},
        "pharmacology": {
            "type": "string",
            "description": "Description of drugs used, including how and when they were administered. Anesthesia(s), "
            "painkiller(s), etc., plus dosage, concentration, etc.",
        },
        "protocol": {
            "type": "string",
            "description": "Experimental protocol, if applicable. E.g., include IACUC protocol",
        },
        "related_publications": {
            "type": "string",
            "description": "Publication information.PMID, DOI, URL, etc. If multiple, concatenate together and describe"
            " which is which. such as PMID, DOI, URL, etc",
        },
        "slices": {
            "type": "string",
            "description": "Description of slices, including information about preparation thickness, orientation, "
            "temperature and bath solution",
        },
        "source_script": {"type": "string", "description": "Script file used to create this NWB file."},
        "source_script_file_name": {"type": "string", "description": "Name of the source_script file"},
        "data_collection": {"type": "string", "description": "Notes about data collection and analysis."},
        "surgery": {
            "type": "string",
            "description": (
                "Narrative description about surgery/surgeries, including date(s) and who performed surgery."
            ),
        },
        "virus": {
            "type": "string",
            "description": "Information about virus(es) used in experiments, including virus ID, source, date made, "
            "injection location, volume, etc.",
        },
        "stimulus_notes": {"type": "string", "description": "Notes about stimuli, such as how and where presented."},
        "lab": {"type": "string", "description": "lab where experiment was performed"},
        "keywords": {
            "description": "Terms to search over",
            "type": "array",
            "items": {"title": "keyword", "type": "string"},
        },
    }
    return schema


def get_metadata_schema_for_icephys():
    schema = get_base_schema(tag="Icephys")
    schema["required"] = ["Device", "Electrode"]
    schema["properties"] = dict(
        Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Icephys/properties/definitions/Device"}),
        Electrode=dict(
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
