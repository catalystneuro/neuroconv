import json
from pathlib import Path
from typing import Union
import os
from copy import deepcopy

from nwb_conversion_tools.utils.json_schema import (
    get_schema_from_method_signature,
    dict_deep_update,
    fill_defaults,
    load_dict_from_file,
)
from nwb_conversion_tools.utils.metadata import load_metadata_from_file


def compare_dicts(a: dict, b: dict):
    a = sort_item(a)
    b = sort_item(b)
    assert json.dumps(a, indent=2) == json.dumps(b, indent=2)


def compare_dicts_2(a: dict, b: dict):
    a = sort_item(a)
    b = sort_item(b)
    assert json.dumps(a) == json.dumps(b)


def sort_item(item):
    if isinstance(item, list):
        return [sort_item(x) for x in sorted(item, key=str)]
    elif isinstance(item, dict):
        return {k: sort_item(item[k]) for k in sorted(item)}
    else:
        return item


def test_get_schema_from_method_signature():
    class A:
        def __init__(self, a: int, b: float, c: Union[Path, str], d: bool, e: str = "hi"):
            pass

    schema = get_schema_from_method_signature(A.__init__)

    correct_schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(type="number"),
            b=dict(type="number"),
            c=dict(type="string"),
            d=dict(type="boolean"),
            e=dict(default="hi", type="string"),
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object",
    )

    compare_dicts(schema, correct_schema)


def test_dict_deep_update_1():
    # 1. test the updating of two dicts with all keys and values as immutable elements
    a1 = dict(a=1, b="hello", c=23)
    b1 = dict(a=3, b="goodbye", d="compare")
    result1 = dict_deep_update(a1, b1)
    correct_result = dict(a=3, b="goodbye", c=23, d="compare")
    compare_dicts(result1, correct_result)


def test_dict_deep_update_2():
    # 2. test dict update with values as dictionaries themselves
    a1 = dict(a=1, b="hello", c=23)
    b1 = dict(a=3, b="goodbye", d="compare")

    a2 = dict(a=1, c=a1)
    b2 = dict(a=3, b="compare", c=b1)
    result2 = dict_deep_update(a2, b2)
    correct_result = dict(a=3, b="compare", c=dict_deep_update(a1, b1))
    compare_dicts(result2, correct_result)


def test_dict_deep_update_3():
    # 3.1 test merge of dicts with a key's value as a list of int/str
    a1 = dict(a=1, b="hello", c=23)
    b1 = dict(a=3, b="goodbye", d="compare")

    a2 = dict(a=1, c=a1)
    b2 = dict(a=3, b="compare", c=b1)

    a3 = dict(a2, ls1=[1, 2, "test"])
    b3 = dict(b2, ls1=[3, 1, "test2"], ls3=[2, 3, "test4"])
    # test whether repeated values are not removed
    result3_1 = dict_deep_update(a3, b3, remove_repeats=False)
    correct_result = dict(dict_deep_update(a2, b2), ls1=[1, 1, 2, 3, "test", "test2"], ls3=[2, 3, "test4"])
    compare_dicts(result3_1, correct_result)
    # test removing repeats
    result3_1 = dict_deep_update(a3, b3)
    correct_result = dict(dict_deep_update(a2, b2), ls1=[1, 2, 3, "test", "test2"], ls3=[2, 3, "test4"])
    compare_dicts(result3_1, correct_result)

    # 3.2 test without append: in this case ls1 would be overwritten
    result3_2 = dict_deep_update(a3, b3, append_list=False)
    correct_result = dict(dict_deep_update(a2, b2), ls1=b3["ls1"], ls3=[2, 3, "test4"])
    compare_dicts(result3_2, correct_result)


def test_dict_deep_update_4():
    # 4. case of dicts with key's values as a list of dicts.
    a1 = dict(a=1, b="hello", c=23)
    b1 = dict(a=3, b="goodbye", d="compare")

    a2 = dict(a=1, c=a1)
    b2 = dict(a=3, b="compare", c=b1)

    a3 = dict(a2, ls1=[1, 2, "test"])
    b3 = dict(b2, ls1=[3, 1, "test2"])

    c1 = dict(a1, b="world", e="string")
    a4 = dict(deepcopy(a3), ls1=[a1, b1])
    b4 = dict(b3, ls1=[c1])
    # compare key is common in both: if the compare key is found in any of the dicts
    #   in the list then those dicts are dict_deep_updated.
    result4 = dict_deep_update(a4, b4, compare_key="a")
    correct_result = dict(dict_deep_update(a3, b3), ls1=[dict_deep_update(a1, c1), b1])
    compare_dicts(result4, correct_result)
    # compare key missing: if compare key is missing then the list is appended always
    result4 = dict_deep_update(a4, b4, compare_key="b")
    correct_result = dict(dict_deep_update(a3, b3), ls1=[a1, c1, b1])
    compare_dicts(result4, correct_result)


def test_fill_defaults():

    schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(type="number"),
            b=dict(type="number"),
            c=dict(type="string"),
            d=dict(type="boolean"),
            e=dict(default="hi", type="string"),
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object",
    )

    defaults = dict(a=3, c="bye", e="new")

    fill_defaults(schema, defaults)

    correct_new_schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(type="number", default=3),
            b=dict(type="number"),
            c=dict(type="string", default="bye"),
            d=dict(type="boolean"),
            e=dict(default="new", type="string"),
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object",
    )

    compare_dicts(schema, correct_new_schema)


def test_load_metadata_from_file():
    m0 = dict(
        NWBFile=dict(
            experimenter="Mr Tester",
            identifier="abc123",
            institution="My University",
            lab="My lab",
            session_description="testing conversion tools software",
            session_start_time="2020-04-15T10:00:00+00:00",
        ),
        Subject=dict(
            description="ADDME",
            sex="M",
            species="ADDME",
            subject_id="sid000",
            weight="10g",
            date_of_birth="2020-04-07T00:15:00+00:00",
        ),
        Ecephys=dict(
            Device=[dict(name="device_ecephys")],
            ElectricalSeries=[
                dict(description="ADDME", name="ElectricalSeries", rate=10.0, starting_time=0.0, conversion=1.0)
            ],
            ElectrodeGroup=[
                dict(description="ADDME", device="device_ecephys", location="ADDME", name="ElectrodeGroup")
            ],
        ),
    )

    yaml_file_path = os.path.join(os.path.dirname(__file__), "metadata_tests.yml")
    json_file_path = os.path.join(os.path.dirname(__file__), "metadata_tests.json")

    m1 = load_dict_from_file(file=yaml_file_path)
    compare_dicts_2(m0, m1)

    m2 = load_dict_from_file(file=json_file_path)
    compare_dicts_2(m0, m2)
