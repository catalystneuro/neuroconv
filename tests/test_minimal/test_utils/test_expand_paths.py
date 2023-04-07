import os
from pathlib import Path

from neuroconv.utils import LocalPathExpander

#  helper functions to test for equivalence between set-like lists of dicts.
def freeze(obj):
    if isinstance(obj, dict):
        return frozenset((k, freeze(v)) for k, v in obj.items())
    elif isinstance(obj, list):
        return frozenset(freeze(x) for x in obj)
    return obj


def are_equivalent_lists(list1, list2):
    set1 = set(freeze(x) for x in list1)
    set2 = set(freeze(x) for x in list2)
    return set1 == set2


def test_expand_paths(tmpdir):

    expander = LocalPathExpander()

    # set up directory for parsing
    base = Path(tmpdir)
    for subject_id in ("001", "002"):
        Path.mkdir(base / f"sub-{subject_id}")
        for session_id in ("101", "102"):
            Path.mkdir(base / f"sub-{subject_id}" / f"session_{session_id}")
            (base / f"sub-{subject_id}" / f"session_{session_id}" / "abc").touch()
            (base / f"sub-{subject_id}" / f"session_{session_id}" / "xyz").touch()

    # run path parsing
    out = expander.expand_paths(
        dict(
            aa=dict(
                folder=base, 
                file_path=os.path.join("sub-{subject_id:3}", "session_{session_id:3}", "abc") 
            ),
            bb=dict(
                folder=base, 
                file_path=os.path.join("sub-{subject_id:3}", "session_{session_id:3}", "xyz")
            ),
        ),
    )

    # test results
    assert are_equivalent_lists(
        out,
        [
            {
                "source_data": {
                    "aa": {"file_path": os.path.join("sub-002", "session_101", "abc")},
                    "bb": {"file_path": os.path.join("sub-002", "session_101", "xyz")},
                },
                "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "002"}},
            },
            {
                "source_data": {
                    "aa": {"file_path": os.path.join("sub-002", "session_102", "abc")},
                    "bb": {"file_path": os.path.join("sub-002", "session_102", "xyz")},
                },
                "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "002"}},
            },
            {
                "source_data": {
                    "aa": {"file_path": os.path.join("sub-001", "session_101", "abc")},
                    "bb": {"file_path": os.path.join("sub-001", "session_101", "xyz")},
                },
                "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "001"}},
            },
            {
                "source_data": {
                    "aa": {"file_path": os.path.join("sub-001", "session_102", "abc")},
                    "bb": {"file_path": os.path.join("sub-001", "session_102", "xyz")},
                },
                "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "001"}},
            },
        ],
    )
