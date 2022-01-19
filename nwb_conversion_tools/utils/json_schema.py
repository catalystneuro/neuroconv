"""Authors: Luiz Tauffer, Cody Baker, Saksham Sharda and Ben Dichter."""
import collections.abc
import inspect
import warnings
from copy import deepcopy
from datetime import datetime
import yaml
import json
from pathlib import Path
from typing import Optional, Union
from typing import TypeVar

import numpy as np
import pynwb

FilePathType = TypeVar("FilePathType", str, Path)
FolderPathType = TypeVar("FolderPathType", str, Path)
OptionalFilePathType = Optional[FilePathType]
OptionalFolderPathType = Optional[FolderPathType]
ArrayType = Union[list, np.ndarray]
OptionalArrayType = Optional[ArrayType]
FloatType = Union[float, np.float]
IntType = Union[int, np.integer]


class NoDatesSafeLoader(yaml.SafeLoader):
    """Custom override of yaml Loader class for datetime considerations."""

    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Remove implicit resolvers for a particular tag.

        Takes care not to modify resolvers in super classes.
        Solution taken from https://stackoverflow.com/a/37958106/11483674
        We want to load datetimes as strings, not dates, because we go on to serialise as jsonwhich doesn't have the
        advanced types of yaml, and leads to incompatibilities down the track.
        """
        if "yaml_implicit_resolvers" not in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


def load_dict_from_file(file_path: FilePathType) -> dict:
    """Safely load metadata from .yml or .json files."""
    file_path = Path(file_path)
    assert file_path.is_file(), f"{file_path} is not a file."
    assert file_path.suffix in [".yml", ".json"], f"{file_path} is not a valid .yml or .json file."

    if file_path.suffix == ".yml":
        with open(file=file_path, mode="r") as stream:
            dictionary = yaml.load(stream=stream, Loader=NoDatesSafeLoader)
    elif file_path.suffix == ".json":
        with open(file=file_path, mode="r") as fp:
            dictionary = json.load(fp=fp)
    return dictionary


def exist_dict_in_list(d, ls):
    """Check if an identical dictionary exists in the list."""
    return any([d == i for i in ls])


def append_replace_dict_in_list(ls, d, compare_key, list_dict_deep_update: bool = True, remove_repeats: bool = True):
    """
    Correctly updates the list ls with the dict d.

    Cases:
    1.  If d is a dict and ls a list of dicts and ints/str, then for a given compare key, if for any element of ls
        (which is a dict) say: ls[3][compare_key] == d[compare_key], then it will dict_deep_update these instead of appending d
        to list ls. Only if compare_key is not present in any of dicts in the list ls, then d is simply appended
        to ls.
    2.  If d is of immutable types like str, int etc, the ls is either appended with d or not.
        This depends on the value of remove_repeats. If remove_repeats is False, then ls is always appended with d.
        If remove_repeats is True, then if value d is present then its not appended else it is.

    Parameters
    ----------
    ls: list
        list of a dicts or int/str or a combination. This is the object to update
    d: list/str/int
        this is the object from which ls is updated.
    compare_key: str
        name of the key for which to check the presence of dicts in ls which need dict_deep_update
    list_dict_deep_update: bool
        whether to update a dict in ls with compare_key present OR simply replace it.
    remove_repeats: bool
        keep repeated values in the updated ls
    Returns
    -------
    ls: list
        updated list
    """
    if not isinstance(ls, list):
        return d
    if isinstance(d, collections.abc.Mapping):
        indxs = np.where(
            [d.get(compare_key, None) == i[compare_key] for i in ls if isinstance(i, collections.abc.Mapping)]
        )[0]
        if len(indxs) > 0:
            for idx in indxs:
                if list_dict_deep_update:
                    ls[idx] = dict_deep_update(ls[idx], d)
                else:
                    ls[idx] = d
        else:
            ls.append(d)
    elif not (d in ls and remove_repeats):
        ls.append(d)
    return ls


def dict_deep_update(
    d: collections.abc.Mapping,
    u: collections.abc.Mapping,
    append_list: bool = True,
    remove_repeats: bool = True,
    copy: bool = True,
    compare_key: str = "name",
    list_dict_deep_update: bool = True,
) -> collections.abc.Mapping:
    """
    Perform an update to all nested keys of dictionary d(input) from dictionary u(updating dict).

    Parameters
    ----------
    d: dict
        dictionary to update
    u: dict
        dictionary to update from
    append_list: bool
        if the item to update is a list, whether to append the lists or replace the list in d
        eg. d = dict(key1=[1,2,3]), u = dict(key1=[3,4,5]).
        If True then updated dictionary d=dict(key1=[1,2,3,4,5]) else d=dict(key1=[3,4,5])
    remove_repeats: bool
        for updating list in d[key] with list in u[key]: if true then remove repeats: list(set(ls))
    copy: bool
        whether to deepcopy the input dict d
    compare_key: str
        the key that is used to compare dicts (and perform update op) and update d[key] when it is a list if dicts.
        example:
            >>> d = {'input': [{'name':'timeseries1', 'desc':'desc1 of d', 'starting_time':0.0}, {'name':'timeseries2', 'desc':'desc2'}]}
            >>> u = ['input': {'name':'timeseries1', 'desc':'desc2 of u', 'unit':'n.a.'}]
            >>> # if compre_key='name' output is below
            >>> output = ['input': {'name':'timeseries1', 'desc':'desc2 of u', 'starting_time':0.0, 'unit':'n.a.'}, {'name':'timeseries2', 'desc':'desc2'}]
            >>> # else the output is:
            >>> # dict with the same key will be updated instead of being appended to the list
            >>> output = ['input': {'name':'timeseries1', 'desc':'desc1 of d', 'starting_time': 0.0}, {'name':'timeseries2', 'desc':'desc2'}, {'name':'timeseries1', 'desc':'desc2 of u', 'unit':'n.a.'}]
    list_dict_deep_update: bool
        for back compatibility, if False, this would work as before:
        example: if True then for the compare_key example, the output would be:
            >>> output = ['input': {'name':'timeseries1', 'desc':'desc2 of u', 'starting_time':0.0, 'unit':'n.a.'}, {'name':'timeseries2', 'desc':'desc2'}]
            >>> # if False:
            >>> output = ['input': {'name':'timeseries1', 'desc':'desc2 of u', 'starting_time':0.0}, {'name':'timeseries2', 'desc':'desc2'}]# unit key is absent since its a replacement
    Returns
    -------
    d: dict
        return the updated dictionary
    """
    if not isinstance(d, collections.abc.Mapping):
        warnings.warn("input to update should be a dict, returning output")
        return u
    if copy:
        d = deepcopy(d)
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = dict_deep_update(d.get(k, None), v, append_list=append_list, remove_repeats=remove_repeats)
        elif append_list and isinstance(v, list):
            for vv in v:
                d[k] = append_replace_dict_in_list(d.get(k, []), vv, compare_key, list_dict_deep_update, remove_repeats)
        else:
            d[k] = v
    return d


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
                    if len(set(param_types)) > 1:
                        raise ValueError(
                            "Conflicting json parameter types were detected from the annotation! "
                            f"{param.annotation.__args__} found."
                        )
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
    }
    return schema
