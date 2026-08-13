"""Gross temporal alignment on the intracellular interfaces.

Both readers hold it through ``BaseIntracellularInterface``, so these run the same assertions over the two of
them: ``interface.alignment.shift_times(delta)`` moves the written series and nothing else about it, and the
shift adds to the placement a converter computes rather than replacing it.

The two fixtures also cover the two timing representations between them. The Axon one is a multi-sweep file
whose inter-sweep gaps make the samples irregular, so it is written as an explicit timestamps vector, and the
Bruker one is a single regular cycle written as ``starting_time`` plus ``rate``.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import (
    AxonIntracellularInterface,
    BrukerVoltageRecordingInterface,
)
from neuroconv.datainterfaces.icephys.axon.axonintracellularconverter import (
    AxonIntracellularConverter,
)

from ..setup_paths import ECEPHY_DATA_PATH

AXON_DATA_PATH = ECEPHY_DATA_PATH / "axon" / "intracellular_data"
AXON_FILE_PATH = AXON_DATA_PATH / "abf2_zero_current_clamp.abf"
# Runs recorded back to back, so the converter has real header start times to place them by.
AXON_RUN_FILE_PATHS = [
    AXON_DATA_PATH / "read_raw_protocol" / "step.abf",
    AXON_DATA_PATH / "read_raw_protocol" / "ramp.abf",
]
BRUKER_DATA_PATH = ECEPHY_DATA_PATH / "bruker" / "voltage_recording"


def build_axon_interface():
    return AxonIntracellularInterface(file_path=AXON_FILE_PATH, response_channel_name="IN0", mode="izero")


def build_bruker_interface():
    cycle_csv_path = next((BRUKER_DATA_PATH / "cc_01_cell1-001").glob("*_VoltageRecording_*.csv"))
    return BrukerVoltageRecordingInterface(file_paths=[cycle_csv_path])


def written_response_series(interface):
    """Write the interface to a fresh in-memory file and return its response series."""
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    return next(iter(nwbfile.acquisition.values()))


def converter_series_starts(converter) -> list[float]:
    """Return the first sample time of every series the converter writes, in a stable order."""
    nwbfile = converter.create_nwbfile()
    return sorted(float(written_times(series)[0]) for series in nwbfile.acquisition.values())


def written_times(series) -> np.ndarray:
    """Return the series' sample times, whichever of the two timing representations it was written in."""
    if series.timestamps is not None:
        return np.asarray(series.timestamps[:])
    return series.starting_time + np.arange(series.data.shape[0]) / series.rate


@pytest.mark.parametrize("build_interface", [build_axon_interface, build_bruker_interface])
def test_shift_moves_the_written_series_and_accumulates(build_interface):
    # Successive shifts add up, and every sample moves by the same amount, so the series keeps its internal
    # timing. A regular one also keeps its rate, since a rigid translation cancels in the sample differences
    # calculate_regular_series_rate measures.
    unshifted_series = written_response_series(build_interface())

    interface = build_interface()
    interface.alignment.shift_times(1.0)
    interface.alignment.shift_times(0.5)
    shifted_series = written_response_series(interface)

    assert_allclose(written_times(shifted_series), written_times(unshifted_series) + 1.5)
    # Approximate because the rate is re-derived from the shifted samples: adding 1.5 to times spaced 1e-4
    # apart costs a few bits, so a 10 kHz series comes back as 10000.0000000011 rather than 10000.0.
    assert shifted_series.rate == pytest.approx(unshifted_series.rate)


def test_shift_moves_a_converter_placed_set_as_a_block():
    # The converter places the files against each other through the same public method, so a user shift after
    # construction adds to that placement instead of replacing it. Two files are the minimum that can show it:
    # with one, every placement is zero and a bug that overwrote the placement would pass unnoticed.
    def build_interfaces():
        return [
            AxonIntracellularInterface(file_path=file_path, response_channel_name="IN0", mode="current_clamp")
            for file_path in AXON_RUN_FILE_PATHS
        ]

    placed_starts = converter_series_starts(AxonIntracellularConverter(data_interfaces=build_interfaces()))

    converter = AxonIntracellularConverter(data_interfaces=build_interfaces())
    for interface in converter.data_interface_objects.values():
        interface.alignment.shift_times(7.0)
    shifted_starts = converter_series_starts(converter)

    # Every series moved by the same seven seconds, so the files keep the placement they were given.
    assert_allclose(shifted_starts, np.asarray(placed_starts) + 7.0)
    # And the placement was a real one, not a set of zeros that any bug would satisfy.
    assert len(set(placed_starts)) == len(AXON_RUN_FILE_PATHS)
