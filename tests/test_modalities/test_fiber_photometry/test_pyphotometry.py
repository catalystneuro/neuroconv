"""Tests for :class:`.PyPhotometryFiberPhotometryInterface` on files built here rather than recorded.

These cover what no available recording can. Header version 1.1 stores an LED-on sample beside the
LED-off baseline it is corrected against, and no public file of that version exists anywhere. And a file
whose header is malformed, or whose mode nothing recognizes, has to be constructed: the interface refuses
those rather than reading them with a default layout, because the format's own fallback rule turns a
laboratory fork's recording into interleaved colours without raising.

Everything a real recording does cover is asserted against the recordings themselves in
``tests/test_on_data/fiber_photometry/test_pyphotometry_interface.py``.
"""

import json

import numpy as np
import pytest

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

VOLTS_PER_DIVISION = 0.00010122


def write_ppd_file(file_path, header: dict, analog_values) -> None:
    """Assemble a ``.ppd`` file: a header length, a JSON header, then the packed words."""
    header_bytes = json.dumps(header).encode("utf-8")
    words = np.asarray(analog_values, dtype=np.uint16) << 1
    file_path.write_bytes(len(header_bytes).to_bytes(2, "little") + header_bytes + words.astype("<u2").tobytes())


def paired_header(version="1.1") -> dict:
    return {
        "subject_ID": "test",
        "date_time": "2025-11-18T10:00:00",
        "mode": "2EX_2EM_pulsed",
        "sampling_rate": 130,
        "volts_per_division": [VOLTS_PER_DIVISION, VOLTS_PER_DIVISION],
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "version": version,
    }


def test_paired_file_writes_the_difference_and_both_measurements(tmp_path):
    """A version 1.1 recording measured twice per sample, and the conversion keeps all of it.

    The response series carries the difference, which is what the board itself wrote before 1.1 and what
    every analysis expects. The LED-on and LED-off measurements are written beside it rather than
    discarded into that subtraction.
    """
    file_path = tmp_path / "paired.ppd"
    # One cycle is four words: signal 1's LED-on and baseline, then signal 2's.
    write_ppd_file(file_path, paired_header(), [1000, 100, 2000, 200, 1010, 110, 2010, 210])
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")

    nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

    acquisition = nwbfile.acquisition
    assert set(acquisition) == {
        "FiberPhotometryResponseSeries",
        "FiberPhotometryResponseSeriesRawLEDOn",
        "FiberPhotometryResponseSeriesRawBaseline",
    }
    assert acquisition["FiberPhotometryResponseSeries"].data == pytest.approx(np.array([900, 900]) * VOLTS_PER_DIVISION)
    assert acquisition["FiberPhotometryResponseSeriesRawLEDOn"].data == pytest.approx(
        np.array([1000, 1010]) * VOLTS_PER_DIVISION
    )
    assert acquisition["FiberPhotometryResponseSeriesRawBaseline"].data == pytest.approx(
        np.array([100, 110]) * VOLTS_PER_DIVISION
    )
    # The three are the same measurement occasion, so they share a timebase.
    for series in acquisition.values():
        assert series.rate == 130.0
        assert series.starting_time == pytest.approx(0.0)


def test_a_recording_without_a_pair_writes_one_series(tmp_path):
    """Before 1.1 the board did the subtraction itself, so there is nothing beside the trace to write."""
    file_path = tmp_path / "unpaired.ppd"
    write_ppd_file(file_path, paired_header(version="1.0"), [1000, 2000, 1010, 2010])
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")

    nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

    assert set(nwbfile.acquisition) == {"FiberPhotometryResponseSeries"}
    assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data == pytest.approx(
        np.array([1000, 1010]) * VOLTS_PER_DIVISION
    )


def test_an_unknown_mode_is_refused(tmp_path):
    """A mode the interface does not know must raise rather than fall back to two signals.

    That fallback is what turns the four-colour fork's recording, which is indistinguishable from an
    ordinary two-signal file except by this string, into interleaved colours that look like a trace.
    """
    file_path = tmp_path / "unknown.ppd"
    header = paired_header() | {"mode": "5EX_3EM_whatever"}
    write_ppd_file(file_path, header, [1000, 2000])

    with pytest.raises(ValueError, match="Unknown pyPhotometry acquisition mode '5EX_3EM_whatever'"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_mode_disagreeing_with_the_declared_signal_count_is_refused(tmp_path):
    """From version 1.0 the header states the count, so a mode contradicting it is not readable."""
    file_path = tmp_path / "contradictory.ppd"
    write_ppd_file(file_path, paired_header() | {"n_analog_signals": 3}, [1000, 2000, 3000])

    with pytest.raises(ValueError, match="interleaves 2 analog lines but the header declares"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def test_a_header_that_is_neither_json_nor_the_fixed_layout_is_refused(tmp_path):
    """A failed JSON parse means the pre-2018 fixed layout, and anything else is not a recording."""
    file_path = tmp_path / "garbage.ppd"
    file_path.write_bytes((8).to_bytes(2, "little") + b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\x00\x00")

    with pytest.raises(ValueError, match="neither JSON nor the 42-byte fixed layout"):
        PyPhotometryFiberPhotometryInterface(file_path=file_path)


def full_metadata(interface) -> dict:
    """The provenance chain a user supplies to write a table: devices, an indicator, and one row."""
    metadata = interface.get_metadata()
    metadata["DeviceModels"] = dict(
        optical_fiber_model=dict(type="OpticalFiberModel", name="optical_fiber_model", numerical_aperture=0.48),
        excitation_source_model=dict(
            type="ExcitationSourceModel",
            name="excitation_source_model",
            source_type="LED",
            excitation_mode="one-photon",
        ),
        photodetector_model=dict(type="PhotodetectorModel", name="photodetector_model", detector_type="photodiode"),
    )
    metadata["Devices"] = dict(
        optical_fiber=dict(
            type="OpticalFiber",
            name="optical_fiber",
            device_model_metadata_key="optical_fiber_model",
            fiber_insertion=dict(depth_in_mm=4.0, insertion_position_ap_in_mm=3.0),
        ),
        excitation_source=dict(
            type="ExcitationSource", name="excitation_source", device_model_metadata_key="excitation_source_model"
        ),
        photodetector=dict(type="Photodetector", name="photodetector", device_model_metadata_key="photodetector_model"),
    )
    fiber_photometry_metadata = metadata["FiberPhotometry"]
    fiber_photometry_metadata["FiberPhotometryIndicators"] = dict(indicator=dict(name="indicator", label="GCaMP6s"))
    fiber_photometry_metadata["FiberPhotometryTable"] = dict(
        name="fiber_photometry_table",
        description="Each row describes a single fiber photometry trace.",
        rows=dict(
            site=dict(
                location="DMS",
                excitation_wavelength_in_nm=470.0,
                emission_wavelength_in_nm=520.0,
                indicator_metadata_key="indicator",
                optical_fiber_metadata_key="optical_fiber",
                excitation_source_metadata_key="excitation_source",
                photodetector_metadata_key="photodetector",
            )
        ),
    )
    series_metadata = fiber_photometry_metadata[interface.metadata_key]
    series_metadata["fiber_photometry_table_region"] = ["site"]
    series_metadata["fiber_photometry_table_region_description"] = "The DMS fiber at 470 nm."
    return metadata


def test_the_led_on_trace_takes_the_channel_row_and_the_baseline_takes_none(tmp_path):
    """The table can describe one of the two raw measurements and not the other.

    Every field of the row is true of the LED-on trace, so it references the same row the difference
    does. The dark measurement was taken with no excitation, and a row has to state an excitation source
    and wavelength, so nothing in the table describes it and it is written unlinked.
    """
    file_path = tmp_path / "paired_linked.ppd"
    write_ppd_file(file_path, paired_header(), [1000, 100, 2000, 200, 1010, 110, 2010, 210])
    interface = PyPhotometryFiberPhotometryInterface(file_path=file_path, stream_name="analog_1")

    nwbfile = interface.create_nwbfile(metadata=full_metadata(interface))

    acquisition = nwbfile.acquisition
    difference_region = acquisition["FiberPhotometryResponseSeries"].fiber_photometry_table_region
    led_on_region = acquisition["FiberPhotometryResponseSeriesRawLEDOn"].fiber_photometry_table_region
    assert list(led_on_region.data) == list(difference_region.data) == [0]
    assert led_on_region.table is difference_region.table
    assert acquisition["FiberPhotometryResponseSeriesRawBaseline"].fiber_photometry_table_region is None
