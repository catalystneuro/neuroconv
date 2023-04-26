from pathlib import Path

from neuroconv.tools import LocalPathExpander


def test_expand_paths(tmpdir):
    expander = LocalPathExpander()

    # set up directory for parsing
    base_directory = Path(tmpdir)
    for subject_id in ("001", "002"):
        Path.mkdir(base_directory / f"sub-{subject_id}")
        for session_id in ("101", "102"):
            Path.mkdir(base_directory / f"sub-{subject_id}" / f"session_{session_id}")
            (base_directory / f"sub-{subject_id}" / f"session_{session_id}" / "abc").touch()
            (base_directory / f"sub-{subject_id}" / f"session_{session_id}" / "xyz").touch()

    # run path parsing
    out = expander.expand_paths(
        dict(
            aa=dict(base_directory=base_directory, file_path="sub-{subject_id:3}/session_{session_id:3}/abc"),
            bb=dict(base_directory=base_directory, file_path="sub-{subject_id:3}/session_{session_id:3}/xyz"),
        ),
    )

    expected = [
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-002" / "session_101" / "abc")},
                "bb": {"file_path": str(base_directory / "sub-002" / "session_101" / "xyz")},
            },
            "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "002"}},
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-002" / "session_102" / "abc")},
                "bb": {"file_path": str(base_directory / "sub-002" / "session_102" / "xyz")},
            },
            "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "002"}},
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-001" / "session_101" / "abc")},
                "bb": {"file_path": str(base_directory / "sub-001" / "session_101" / "xyz")},
            },
            "metadata": {"NWBFile": {"session_id": "101"}, "Subject": {"subject_id": "001"}},
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-001" / "session_102" / "abc")},
                "bb": {"file_path": str(base_directory / "sub-001" / "session_102" / "xyz")},
            },
            "metadata": {"NWBFile": {"session_id": "102"}, "Subject": {"subject_id": "001"}},
        },
    ]

    # test results
    for x in out:
        assert x in expected
    assert len(out) == len(expected)
    
    # test again with string inputs to `base_directory`
    string_directory_out = expander.expand_paths(
        dict(
            aa=dict(base_directory=str(base_directory), file_path="sub-{subject_id:3}/session_{session_id:3}/abc"),
            bb=dict(base_directory=str(base_directory), file_path="sub-{subject_id:3}/session_{session_id:3}/xyz"),
        ),
    )
    for x in string_directory_out:
        assert x in expected
    assert len(string_directory_out) == len(expected)
