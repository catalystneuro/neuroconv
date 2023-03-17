from pathlib import Path

from neuroconv.utils.globbing import unpack_experiment_dynamic_paths


def test_unpack_experiment_dynamic_paths(tmpdir):
    base = Path(tmpdir)
    for subject_id in ("001", "002"):
        Path.mkdir(base / f"sub-{subject_id}")
        for session_id in ("101", "102"):
            Path.mkdir(base / f"sub-{subject_id}" / f"session_{session_id}")
            (base / f"sub-{subject_id}" / f"session_{session_id}" / "abc").touch()
            (base / f"sub-{subject_id}" / f"session_{session_id}" / "xyz").touch()

    out = unpack_experiment_dynamic_paths(
        base,
        dict(
            aa=dict(file_path="sub-{subject_id:3}/session_{session_id:3}/abc"),
            bb=dict(file_path="sub-{subject_id:3}/session_{session_id:3}/xyz"),
        ),
    )

    print(out)

    assert out == [
        {
            "source_data": {
                "aa": {"file_path": "sub-002/session_101/abc"},
                "bb": {"file_path": "sub-002/session_101/xyz"},
            },
            "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "002"}},
        },
        {
            "source_data": {
                "aa": {"file_path": "sub-002/session_102/abc"},
                "bb": {"file_path": "sub-002/session_102/xyz"},
            },
            "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "002"}},
        },
        {
            "source_data": {
                "aa": {"file_path": "sub-001/session_101/abc"},
                "bb": {"file_path": "sub-001/session_101/xyz"},
            },
            "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "001"}},
        },
        {
            "source_data": {
                "aa": {"file_path": "sub-001/session_102/abc"},
                "bb": {"file_path": "sub-001/session_102/xyz"},
            },
            "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "001"}},
        },
    ]
