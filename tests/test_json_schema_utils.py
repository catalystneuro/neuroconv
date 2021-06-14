import json
from pathlib import Path
from typing import Union

from nwb_conversion_tools.utils.json_schema import get_schema_from_method_signature, dict_deep_update, fill_defaults


def compare_dicts(a: dict, b: dict):
    assert json.dumps(a, sort_keys=True, indent=2) == json.dumps(b, sort_keys=True, indent=2)


def test_get_schema_from_method_signature():
    class A:
        def __init__(self, a: int, b: float, c: Union[Path, str], d: bool, e: str = 'hi'):
            pass

    schema = get_schema_from_method_signature(A.__init__)

    correct_schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(type="number"),
            b=dict(type="number"),
            c=dict(type="string"),
            d=dict(type="boolean"),
            e=dict(
                default="hi",
                type="string"
            )
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object"
    )

    compare_dicts(schema, correct_schema)


def test_dict_deep_update():

    a = dict(
        a=1,
        b='hello',
        c=dict(
            a=2
        ),
        d=[1, 2, 3]
    )

    b = dict(
        a=3,
        b='goodbye',
        c=dict(
            b=1
        ),
        d=[4, 5, 6]
    )

    result = dict_deep_update(a, b)

    correct_result = {'a': 3, 'b': 'goodbye', 'c': {'a': 2, 'b': 1}, 'd': [1, 2, 3, 4, 5, 6]}

    compare_dicts(result, correct_result)

    result2 = dict_deep_update(a, b, append_list=False)

    correct_result2 = {'a': 3, 'b': 'goodbye', 'c': {'a': 2, 'b': 1}, 'd': [4, 5, 6]}

    compare_dicts(result2, correct_result2)


def test_fill_defaults():

    schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(type="number"),
            b=dict(type="number"),
            c=dict(type="string"),
            d=dict(type="boolean"),
            e=dict(
                default="hi",
                type="string"
            )
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object"
    )

    defaults = dict(
        a=3,
        c="bye",
        e="new"
    )

    fill_defaults(schema, defaults)

    correct_new_schema = dict(
        additionalProperties=False,
        properties=dict(
            a=dict(
                type="number",
                default=3
            ),
            b=dict(type="number"),
            c=dict(
                type="string",
                default="bye"
            ),
            d=dict(type="boolean"),
            e=dict(
                default="new",
                type="string"
            )
        ),
        required=[
            "a",
            "b",
            "c",
            "d",
        ],
        type="object"
    )

    compare_dicts(schema, correct_new_schema)
