import json
from pathlib import Path
from typing import Union
import os

from nwb_conversion_tools.utils.json_schema import get_schema_from_method_signature, dict_deep_update, fill_defaults
from nwb_conversion_tools.utils.metadata import load_metadata_from_file


def compare_dicts(a: dict, b: dict):
    assert json.dumps(a, sort_keys=True, indent=2) == json.dumps(b, sort_keys=True, indent=2)


def compare_dicts_2(a: dict, b: dict):
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


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


def test_load_metadata_from_file():
    m0 = dict(
        NWBFile=dict(
            experimenter='Mr Tester',
            identifier='abc123',
            institution='My University',
            lab='My lab',
            session_description='testing conversion tools software',
            session_start_time='2020-04-15T10:00:00+00:00'
        ),
        Subject=dict(
            description='ADDME',
            sex='M',
            species='ADDME',
            subject_id='sid000',
            weight='10g',
            date_of_birth='2020-04-07T00:15:00+00:00'
        ),
        Ecephys=dict(
            Device=[
                dict(
                    name='device_ecephys'
                )
            ],
            ElectricalSeries=[
                dict(
                    description='ADDME',
                    name='ElectricalSeries',
                    rate=10.0,
                    starting_time=0.0,
                    conversion=1.0
                )
            ],
            ElectrodeGroup=[
                dict(
                    description='ADDME',
                    device='device_ecephys',
                    location='ADDME',
                    name='ElectrodeGroup'
                )
            ]
        )
    )

    yaml_file = os.path.join(os.path.dirname(__file__), 'metadata_tests.yml')
    json_file = os.path.join(os.path.dirname(__file__), 'metadata_tests.json')
    
    m1 = load_metadata_from_file(file=yaml_file)
    compare_dicts_2(m0, m1)

    m2 = load_metadata_from_file(file=json_file)
    compare_dicts_2(m0, m2)