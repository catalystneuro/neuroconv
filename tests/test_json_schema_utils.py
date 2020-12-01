import json
from pathlib import Path
from typing import Union

from nwb_conversion_tools.json_schema_utils import get_schema_from_method_signature


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

    assert json.dumps(schema, sort_keys=True, indent=2) == json.dumps(correct_schema, sort_keys=True, indent=2)
