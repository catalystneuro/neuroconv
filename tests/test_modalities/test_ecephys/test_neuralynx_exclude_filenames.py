"""Generates synthetic files with different sampling rates and gaps to cause "incompatible section structures" error

Headers reproducted from Pegasus recordings in MNE test data
"""

from pathlib import Path

import numpy as np
import pytest

from neuroconv.datainterfaces import (
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
)

NCS_RECORD_DTYPE = np.dtype(
    [
        ("timestamp", "<u8"),
        ("channel_id", "<u4"),
        ("sample_rate", "<u4"),
        ("nb_valid", "<u4"),
        ("samples", "<i2", (512,)),
    ]
)


def _write_ncs(
    file_path: Path,
    channel_id: int,
    sampling_frequency: float,
    input_range_uv: int,
    dsp_high_cut_frequency: int,
    num_records: int,
    gap_after_record: int | None = None,
    gap_us: int = 0,
) -> None:
    """Write a Pegasus 2.1.3 style `.ncs` file with a 16 kB text header followed by 512-sample records"""
    name = file_path.stem
    header_lines = [
        "######## Neuralynx Data File Header",
        "-FileType NCS",
        "-FileVersion 3.4",
        "-ProbeName ",
        f'-OriginalFileName "E:\\Data\\2024-01-01_00-00-00\\{name}.ncs"',
        "-TimeCreated 2024/01/01 00:00:00",
        "-TimeClosed 2024/01/01 00:10:00",
        "",
        "-RecordSize 1044",
        '-ApplicationName Pegasus "2.1.3 "',
        "-AcquisitionSystem AcqSystem1 ATLAS",
        '-ReferenceChannel "Source 01 Reference 1"',
        f"-SamplingFrequency {int(sampling_frequency)}",
        "-ADMaxValue 32767",
        f"-ADBitVolts {input_range_uv * 1e-6 / 32768:.24f}",
        f"-AcqEntName {name}",
        "-NumADChannels 1",
        f"-ADChannel {channel_id}",
        f"-InputRange {input_range_uv}",
        "-InputInverted True",
        "",
        "-DSPLowCutFilterEnabled True",
        "-DspLowCutFrequency 0.1",
        "-DspLowCutNumTaps 0",
        "-DspLowCutFilterType DCO",
        "-DSPHighCutFilterEnabled True",
        f"-DspHighCutFrequency {dsp_high_cut_frequency}",
        "-DspHighCutNumTaps 256",
        "-DspHighCutFilterType FIR",
        "-DspDelayCompensation Enabled",
        "-DspFilterDelay_µs 3984",
    ]
    header = ("\r\n".join(header_lines) + "\r\n").encode("latin-1").ljust(2**14, b"\x00")

    records = np.zeros(num_records, dtype=NCS_RECORD_DTYPE)
    record_duration_us = 512 / sampling_frequency * 1e6
    records["timestamp"] = np.round(np.arange(num_records) * record_duration_us).astype("u8")
    if gap_after_record is not None:
        records["timestamp"][gap_after_record:] += gap_us
    records["channel_id"] = channel_id
    records["sample_rate"] = int(sampling_frequency)
    records["nb_valid"] = 512
    records["samples"] = np.random.default_rng(channel_id).integers(-1000, 1000, size=(num_records, 512), dtype="i2")

    file_path.write_bytes(header + records.tobytes())


@pytest.fixture
def mixed_streams_folder(tmp_path) -> Path:
    micro = dict(sampling_frequency=32000.0, input_range_uv=1000, dsp_high_cut_frequency=8000)
    macro = dict(sampling_frequency=2000.0, input_range_uv=10000, dsp_high_cut_frequency=500)
    _write_ncs(tmp_path / "LAHCu1.ncs", channel_id=136, num_records=20, **micro)
    _write_ncs(tmp_path / "LAHCu2.ncs", channel_id=137, num_records=20, **micro)
    # 2 kHz channel with a 100 ms pause after its second record, so it has two sections and the 32 kHz stream one
    _write_ncs(tmp_path / "LAHC1.ncs", channel_id=8, num_records=4, gap_after_record=2, gap_us=100_000, **macro)
    return tmp_path


def test_recording_without_exclude_filenames_raises(mixed_streams_folder):
    with pytest.raises(ValueError, match="Incompatible section structures across streams"):
        NeuralynxRecordingInterface(
            folder_path=mixed_streams_folder,
            stream_name="stream0_32000Hz_1mVRange_DSPFilter0",
            gap_tolerance_ms=1.0,
        )


def test_recording_exclude_filenames(mixed_streams_folder):
    interface = NeuralynxRecordingInterface(
        folder_path=mixed_streams_folder,
        exclude_filenames=["LAHC1.ncs"],
        gap_tolerance_ms=1.0,
    )
    recording = interface.recording_extractor
    assert recording.get_sampling_frequency() == 32000.0
    assert recording.get_num_segments() == 1
    assert recording.get_num_samples() == 20 * 512
    assert recording.get_channel_ids().tolist() == ["136", "137"]

    # The timestamps are read by building the extractor again from the interface arguments
    timestamps = interface._get_original_timestamps()
    assert len(timestamps) == 20 * 512


def test_recording_exclude_filenames_other_stream(mixed_streams_folder):
    interface = NeuralynxRecordingInterface(
        folder_path=mixed_streams_folder,
        exclude_filenames=["LAHCu1.ncs", "LAHCu2.ncs"],
        gap_tolerance_ms=1.0,
    )
    recording = interface.recording_extractor
    assert recording.get_sampling_frequency() == 2000.0
    assert recording.get_num_segments() == 2
    assert recording.get_channel_ids().tolist() == ["8"]


def test_get_stream_names_exclude_filenames(mixed_streams_folder):
    with pytest.raises(ValueError, match="Incompatible section structures across streams"):
        NeuralynxRecordingInterface.get_stream_names(folder_path=mixed_streams_folder)

    stream_names = NeuralynxRecordingInterface.get_stream_names(
        folder_path=mixed_streams_folder, exclude_filenames=["LAHC1.ncs"]
    )
    assert stream_names == ["stream0_32000Hz_1mVRange_DSPFilter0"]


def test_sorting_exclude_filenames(mixed_streams_folder):
    with pytest.raises(ValueError, match="Incompatible section structures across streams"):
        NeuralynxSortingInterface(folder_path=mixed_streams_folder, gap_tolerance_ms=1.0)

    interface = NeuralynxSortingInterface(
        folder_path=mixed_streams_folder,
        exclude_filenames=["LAHC1.ncs"],
        gap_tolerance_ms=1.0,
    )
    assert interface.sorting_extractor.get_sampling_frequency() == 32000.0
