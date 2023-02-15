import os

from neuroconv.utils import generate_regex_from_fstring, glob_pattern


def test_generate_regex_from_fstring():
    fstring = "sub-{subject_id}/sub-{subject_id}/ses-{session_id}"
    pattern = "sub-(?P<subject_id>.+)/sub-(?P=subject_id)/ses-(?P<session_id>.+)"
    assert generate_regex_from_fstring(fstring) == pattern


def test_glob_pattern(tmpdir):
    pattern = os.path.join(
        "sub-(?P<subject_id>.+)",
        "sub-(?P=subject_id)_ses-(?P<session_id>.+)",
    )

    data = [
        {"subject_id": "002", "session_id": "a"},
        {"subject_id": "001", "session_id": "a"},
        {"subject_id": "001", "session_id": "b"},
    ]

    # set up folders
    for d in data:
        os.makedirs(os.path.join(tmpdir, f"sub-{d['subject_id']}", f"sub-{d['subject_id']}_ses-{d['session_id']}"))

    out = glob_pattern(tmpdir, pattern)
    assert out == {
        os.path.join(tmpdir, f"sub-{d['subject_id']}", f"sub-{d['subject_id']}_ses-{d['session_id']}"): dict(
            subject_id=d["subject_id"], session_id=d["session_id"]
        )
        for d in data
    }
