import json
import unittest
from datetime import datetime
from pathlib import Path

import pytest

from neuroconv.tools import LocalPathExpander
from neuroconv.tools.testing import generate_path_expander_demo_ibl
from neuroconv.utils import NWBMetaDataEncoder


def test_only_folder_match(tmpdir):
    base_directory = Path(tmpdir)

    sub_directory1 = base_directory / "a_simple_pattern_1"
    sub_directory2 = base_directory / "a_simple_pattern_2"

    sub_directory1.mkdir(exist_ok=True)
    sub_directory2.mkdir(exist_ok=True)

    # Add files with the same name to both folders
    file1 = sub_directory1 / "a_simple_pattern_1.bin"
    file2 = sub_directory2 / "a_simple_pattern_2.bin"

    # Create files
    file1.touch()
    file2.touch()

    # Add another sub-nested folder with a folder
    sub_directory3 = sub_directory1 / "a_simple_pattern_3"
    sub_directory3.mkdir(exist_ok=True)
    file3 = sub_directory3 / "a_simple_pattern_3.bin"
    file3.touch()

    # Specify source data (note this assumes the files are arranged in the same way as in the example data)
    source_data_spec = {
        "a_source": {
            "base_directory": base_directory,
            "folder_path": "a_simple_pattern_{session_id}",
        }
    }

    # Instantiate LocalPathExpander

    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)
    folder_paths = [metadata_match["source_data"]["a_source"]["folder_path"] for metadata_match in metadata_list]

    expected = {str(sub_directory1), str(sub_directory2), str(sub_directory3)}

    assert set(folder_paths) == expected


def test_only_file_match(tmpdir):
    base_directory = Path(tmpdir)

    sub_directory1 = base_directory / "a_simple_pattern_1"
    sub_directory2 = base_directory / "a_simple_pattern_2"

    sub_directory1.mkdir(exist_ok=True)
    sub_directory2.mkdir(exist_ok=True)

    # Add files with the same name to both folders
    file1 = sub_directory1 / "a_simple_pattern_1.bin"
    file2 = sub_directory2 / "a_simple_pattern_2.bin"

    # Create files
    file1.touch()
    file2.touch()

    # Add another sub-nested folder with a folder
    sub_directory3 = sub_directory1 / "a_simple_pattern_3"
    sub_directory3.mkdir(exist_ok=True)
    file3 = sub_directory3 / "a_simple_pattern_3.bin"
    file3.touch()

    # Specify source data (note this assumes the files are arranged in the same way as in the example data)
    source_data_spec = {
        "a_source": {
            "base_directory": base_directory,
            "file_path": "a_simple_pattern_{session_id}.bin",
        }
    }

    # Instantiate LocalPathExpander

    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)
    file_paths = [metadata_match["source_data"]["a_source"]["file_path"] for metadata_match in metadata_list]

    expected = {str(file1), str(file2), str(file3)}
    assert set(file_paths) == expected


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
    metadata_list = expander.expand_paths(
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
    for x in metadata_list:
        assert x in expected
    assert len(metadata_list) == len(expected)

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


def test_expand_paths_with_extras(tmpdir):
    expander = LocalPathExpander()

    # set up directory for parsing
    base_directory = Path(tmpdir)
    for area_and_modality in ("V1_eeg", "S1_2p"):
        for subject_id in ("001", "002"):
            for session_id, session_start_time in (("101", datetime(2021, 1, 1)), ("102", datetime(2021, 1, 2))):
                Path.mkdir(
                    base_directory / f"{area_and_modality}" / f"sub-{subject_id}" / f"session_{session_id}",
                    parents=True,
                )
                (
                    base_directory
                    / f"{area_and_modality}"
                    / f"sub-{subject_id}"
                    / f"session_{session_id}"
                    / f"{session_start_time:%Y-%m-%d}abc"
                ).touch()
                (
                    base_directory
                    / f"{area_and_modality}"
                    / f"sub-{subject_id}"
                    / f"session_{session_id}"
                    / f"{session_start_time:%Y-%m-%d}xyz"
                ).touch()

    # run path parsing
    out = expander.expand_paths(
        dict(
            aa=dict(
                base_directory=base_directory,
                file_path="{recording_area}_{modality}/sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}abc",
            ),
            bb=dict(
                base_directory=base_directory,
                file_path="{recording_area}_{modality}/sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}xyz",
            ),
        ),
    )

    expected = [
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "V1_eeg" / "sub-002" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "V1_eeg" / "sub-002" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "002"},
                "extras": {"recording_area": "V1", "modality": "eeg"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "V1_eeg" / "sub-002" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "V1_eeg" / "sub-002" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "002"},
                "extras": {"recording_area": "V1", "modality": "eeg"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "V1_eeg" / "sub-001" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "V1_eeg" / "sub-001" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "001"},
                "extras": {"recording_area": "V1", "modality": "eeg"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "V1_eeg" / "sub-001" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "V1_eeg" / "sub-001" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "001"},
                "extras": {"recording_area": "V1", "modality": "eeg"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "S1_2p" / "sub-002" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "S1_2p" / "sub-002" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "002"},
                "extras": {"recording_area": "S1", "modality": "2p"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "S1_2p" / "sub-002" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "S1_2p" / "sub-002" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "002"},
                "extras": {"recording_area": "S1", "modality": "2p"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "S1_2p" / "sub-001" / "session_101" / "2021-01-01abc")},
                "bb": {"file_path": str(base_directory / "S1_2p" / "sub-001" / "session_101" / "2021-01-01xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "101", "session_start_time": datetime(2021, 1, 1)},
                "Subject": {"subject_id": "001"},
                "extras": {"recording_area": "S1", "modality": "2p"},
            },
        },
        {
            "source_data": {
                "aa": {"file_path": str(base_directory / "S1_2p" / "sub-001" / "session_102" / "2021-01-02abc")},
                "bb": {"file_path": str(base_directory / "S1_2p" / "sub-001" / "session_102" / "2021-01-02xyz")},
            },
            "metadata": {
                "NWBFile": {"session_id": "102", "session_start_time": datetime(2021, 1, 2)},
                "Subject": {"subject_id": "001"},
                "extras": {"recording_area": "S1", "modality": "2p"},
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
                file_path="{recording_area}_{modality}/sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}abc",
            ),
            bb=dict(
                base_directory=str(base_directory),
                file_path="{recording_area}_{modality}/sub-{subject_id:3}/session_{session_id:3}/{session_start_time:%Y-%m-%d}xyz",
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
    path_expansion_results = expander.expand_paths(
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
    path_expansion_results = json.loads(json.dumps(path_expansion_results, cls=NWBMetaDataEncoder))

    # build expected output from file
    expected_file_path = Path(__file__).parent / "expand_paths_ibl_expected.json"
    with open(expected_file_path, "r") as f:
        expected = json.load(f)
    for entry in expected:
        for source_data in entry["source_data"].values():  # update paths with base_directory
            if "file_path" in source_data.keys():
                source_data["file_path"] = str(base_directory / source_data["file_path"])
            if "folder_path" in source_data.keys():
                source_data["folder_path"] = str(base_directory / source_data["folder_path"])

    tc = unittest.TestCase()
    tc.assertCountEqual(path_expansion_results, expected)
