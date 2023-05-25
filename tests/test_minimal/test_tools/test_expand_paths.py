from datetime import datetime
from pathlib import Path

from neuroconv.tools import LocalPathExpander
from neuroconv.tools.testing import generate_path_expander_demo_ibl


def test_expand_paths(tmpdir):
    expander = LocalPathExpander()

    # set up directory for parsing
    base_directory = Path(tmpdir)
    for subject_id in ("001", "002"):
        Path.mkdir(base_directory / f"sub-{subject_id}")
        for session_id, session_start_time in (("101", datetime(2021, 1, 1)), ("102", datetime(2021, 1, 2))):
            Path.mkdir(base_directory / f"sub-{subject_id}" / f"session_{session_id}")
            (
                base_directory / f"sub-{subject_id}" / f"session_{session_id}" / f"{session_start_time:%Y-%m-%d}abc"
            ).touch()
            (
                base_directory / f"sub-{subject_id}" / f"session_{session_id}" / f"{session_start_time:%Y-%m-%d}xyz"
            ).touch()

    # run path parsing
    out = expander.expand_paths(
        dict(
            aa=dict(
                base_directory=base_directory,
                file_path="sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}abc",
            ),
            bb=dict(
                base_directory=base_directory,
                file_path="sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}xyz",
            ),
        ),
    )

    expected = [
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-002" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "sub-002" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "002"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-002" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "sub-002" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "002"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-001" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "sub-001" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "001"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "sub-001" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "sub-001" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "001"},
            },
        },
    ]

    # test results
    for x in out:
        assert x in expected
    assert len(out) == len(expected)

    # test again with string inputs to `base_directory`
    string_directory_out = expander.expand_paths(
        dict(
            aa=dict(
                base_directory=str(base_directory),
                file_path="sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}abc",
            ),
            bb=dict(
                base_directory=str(base_directory),
                file_path="sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}xyz",
            ),
        ),
    )
    for x in string_directory_out:
        assert x in expected
    assert len(string_directory_out) == len(expected)


def test_expand_paths_ibl(tmpdir):
    expander = LocalPathExpander()

    # set up IBL Steinmetz video file structure
    generate_path_expander_demo_ibl(tmpdir)
    base_directory = Path(tmpdir)

    # NOTE: empty brackets used b/c for some reason NR_0021/2022-06-30/ subdir is 002/ instead of 001/
    out = expander.expand_paths(
        dict(
            ibl_video_file=dict(
                base_directory=base_directory,
                file_path="steinmetzlab/Subjects/{subject_id}/{session_start_time:%Y-%m-%d}/{}/raw_video_data/_iblrig_leftCamera.raw.{session_id}.mp4",
            ),
            ibl_video_directory=dict(
                base_directory=base_directory,
                folder_path="steinmetzlab/Subjects/{subject_id}/{session_start_time:%Y-%m-%d}/{}/raw_video_data",
            ),
        ),
    )

    # build expected output with glob and manual parsing
    expected = []
    for file_path in base_directory.glob("steinmetzlab/Subjects/*/*/*/raw_video_data/_iblrig_leftCamera.raw.*.mp4"):
        subject_id = file_path.parts[-5]
        session_start_time = datetime.strptime(file_path.parts[-4], "%Y-%m-%d")
        session_id = file_path.parts[-1].split('.')[-2]
        expected.append({
            "source_data": {
                "ibl_video_file": {"file_path": str(file_path)},
            },
            "metadata": {
                "NWBFile": {"session_id": session_id, "session_start_time": session_start_time},
                "Subject": {"subject_id": subject_id},
            },
        })
    for folder_path in base_directory.glob("steinmetzlab/Subjects/*/*/*/raw_video_data/"):
        subject_id = folder_path.parts[-4]
        session_start_time = datetime.strptime(folder_path.parts[-3], "%Y-%m-%d")
        expected.append({
            "source_data": {
                "ibl_video_directory": {"folder_path": str(folder_path)},
            },
            "metadata": {
                "NWBFile": {"session_start_time": session_start_time},
                "Subject": {"subject_id": subject_id},
            },
        })
    
    # test results
    for x in out:
        assert x in expected
    assert len(out) == len(expected)
