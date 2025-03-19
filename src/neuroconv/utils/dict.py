import collections.abc
import json
import warnings
from collections import defaultdict
from copy import deepcopy
from ctypes import Union
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import yaml
from pydantic import FilePath


class _NoDatesSafeLoader(yaml.SafeLoader):
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


_NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


def load_dict_from_file(file_path: FilePath) -> dict[str, Any]:
    """Safely load metadata from .yml or .json files."""
    file_path = Path(file_path)
    assert file_path.is_file(), f"{file_path} is not a file."
    assert file_path.suffix in (".json", ".yml", ".yaml"), f"{file_path} is not a valid yaml or .json file."

    if file_path.suffix in (".yml", ".yaml"):
        with open(file=file_path, mode="r") as stream:
            dictionary = yaml.load(stream=stream, Loader=_NoDatesSafeLoader)
    elif file_path.suffix == ".json":
        with open(file=file_path, mode="r") as fp:
            dictionary = json.load(fp=fp)
    return dictionary


def exist_dict_in_list(d: dict[str, Any], ls: list[dict[str, Any]]) -> bool:
    """Check if an identical dictionary exists in the list."""
    return any([d == i for i in ls])


def append_replace_dict_in_list(
    ls: list[dict[str, Any]],
    d: dict[str, Any],
    compare_key: str,
    list_dict_deep_update: bool = True,
    remove_repeats: bool = True,
) -> list[dict[str, Any]]:
    """
    Update the list ls with the dict d.

    Cases:

    1.  If d is a dict and ls a list of dicts and ints/str, then for a given compare key, if for any element of ls
        (which is a dict) say: ``ls[3][compare_key] == d[compare_key]``, then it will dict_deep_update these instead of
        appending d to list ls. Only if compare_key is not present in any of dicts in the list ls, then d is simply
        appended to ls.
    2.  If ``d`` is of immutable types like str, int etc., the ls is either appended with ``d`` or not.
        This depends on the value of ``remove_repeats``. If ``remove_repeats`` is ``False``, then ls is always appended with d.
        If ``remove_repeats`` is ``True``, then if value d is present then it is not appended else it is.

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
    d: dict[str, Any],
    u: dict[str, Any],
    append_list: bool = True,
    remove_repeats: bool = True,
    copy: bool = True,
    compare_key: str = "name",
    list_dict_deep_update: bool = True,
) -> dict[str, Any]:
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
        e.g. d = dict(key1=[1,2,3]), u = dict(key1=[3,4,5]).
        If True then updated dictionary d=dict(key1=[1,2,3,4,5]) else d=dict(key1=[3,4,5])
    remove_repeats: bool
        for updating list in d[key] with list in u[key]: if true then remove repeats: list(set(ls))
    copy: bool
        whether to deepcopy the input dict d
    compare_key: str
        the key that is used to compare dicts (and perform update op) and update d[key] when it is a list if dicts.
        example::

            d = {
                [
                    {"name": "timeseries1", "desc": "desc1 of d", "starting_time": 0.0},
                    {"name": "timeseries2", "desc": "desc2"},
                ]
            }
            u = [{"name": "timeseries1", "desc": "desc2 of u", "unit": "n.a."}]
            # if compare_key='name' output is below
            output = [
                {"name": "timeseries1", "desc": "desc2 of u", "starting_time": 0.0, "unit": "n.a."},
                {"name": "timeseries2", "desc": "desc2"},
            ]
            # else the output is:
            # dict with the same key will be updated instead of being appended to the list
            output = [
                {"name": "timeseries1", "desc": "desc1 of d", "starting_time": 0.0},
                {"name": "timeseries2", "desc": "desc2"},
                {"name": "timeseries1", "desc": "desc2 of u", "unit": "n.a."},
            ]

    list_dict_deep_update: bool
        for back compatibility, if False, this would work as before:
        example: if True then for the compare_key example, the output would be::

            output = [
                {"name": "timeseries1", "desc": "desc2 of u", "starting_time": 0.0, "unit": "n.a."},
                {"name": "timeseries2", "desc": "desc2"},
            ]
            # if False:
            output = [
                {"name": "timeseries1", "desc": "desc2 of u", "starting_time": 0.0},
                {"name": "timeseries2", "desc": "desc2"},
            ]  # unit key is absent since it is a replacement
    Returns
    -------
    d: dict
        return the updated dictionary
    """

    dict_to_update, dict_with_update_values = d, u
    if not isinstance(dict_to_update, collections.abc.Mapping):
        warnings.warn("input to update should be a dict, returning output")
        return dict_with_update_values

    if copy:
        dict_to_update = deepcopy(dict_to_update)

    for key_to_update, update_values in dict_with_update_values.items():
        # Update with a dict like object is recursive until an empty dict is found.
        if isinstance(update_values, collections.abc.Mapping):
            sub_dict_to_update = dict_to_update.get(key_to_update, dict())
            sub_dict_with_update_values = update_values
            dict_to_update[key_to_update] = dict_deep_update(
                sub_dict_to_update, sub_dict_with_update_values, append_list=append_list, remove_repeats=remove_repeats
            )
        # Update with list calls the append_replace_dict_in_list function
        elif append_list and isinstance(update_values, list):
            for value in update_values:
                dict_or_list_of_dicts = dict_to_update.get(key_to_update, [])
                dict_to_update[key_to_update] = append_replace_dict_in_list(
                    dict_or_list_of_dicts, value, compare_key, list_dict_deep_update, remove_repeats
                )
        # Update with something else
        else:
            dict_to_update[key_to_update] = update_values

    return dict_to_update


class DeepDict(defaultdict):
    """A defaultdict of defaultdicts"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """A defaultdict of defaultdicts"""
        super().__init__(lambda: DeepDict(), *args, **kwargs)
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = DeepDict(value)

    def deep_update(self, other: Optional[Union[dict[str, Any], "DeepDict"]] = None, **kwargs: Any) -> None:
        """
        Recursively update the DeepDict with another dictionary or DeepDict.

        Parameters
        ----------
        other : dict or DeepDict, optional
            The dictionary or DeepDict to update the current instance with.
        **kwargs : Any
            Additional keyword arguments representing key-value pairs to update the DeepDict.

        Notes
        -----
        For any keys that exist in both the current instance and the provided dictionary, the values are merged
        recursively if both are dictionaries. Otherwise, the value from `other` or `kwargs` will overwrite the
        existing value.
        """
        for key, value in (other or kwargs).items():
            if key in self and isinstance(self[key], dict) and isinstance(value, dict):
                self[key].deep_update(value)
            else:
                self[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Turn a DeepDict into a normal dictionary"""

        def _to_dict(d: Union[dict[str, Any], "DeepDict"]) -> dict[str, Any]:
            return {key: _to_dict(value) for key, value in d.items()} if isinstance(d, dict) else d

        return _to_dict(self)

    def __deepcopy__(self, memodict: dict = {}) -> "DeepDict":
        return DeepDict(deepcopy(self.to_dict()))

    def __repr__(self) -> str:
        return "DeepDict: " + dict.__repr__(self.to_dict())
