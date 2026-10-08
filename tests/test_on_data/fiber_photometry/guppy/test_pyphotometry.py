"""Tests for the pyPhotometry seam of ``GuppyConverter``.

Only what is specific to ``acquisition_format="pyphotometry"``. Everything format-independent -- role
grouping, fiber-region linking, event merging, the registries -- is asserted once in
``test_reference_session``.

GuPPy names a pyPhotometry store exactly as the interfaces name their streams and lines, so the seam
needs no translation. What it does need is one interface per series: the board samples no two of its
signals at the same instant, so a role can hold one store, which is one recording site.

Each class stages its one ``.ppd`` file into ``tmp_path``, because a GuPPy session folder must hold
exactly one recording.
"""

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv.converters import GuppyConverter
from neuroconv.datainterfaces.fiber_photometry.guppy.pyphotometry_utils import (
    build_pyphotometry_acquisition_interface,
    resolve_ppd_file,
)
from neuroconv.datainterfaces.fiber_photometry.pyphotometry._file_reader import (
    _read_ppd,
)
from neuroconv.tools.testing import generate_mock_guppy_output_folder
from neuroconv.utils import dict_deep_update

from ._metadata import (
    build_device_metadata,
    build_fiber_photometry_metadata,
    build_series_metadata,
)
from ...setup_paths import OPHYS_DATA_PATH

# One photodetector read under two excitations strobed in turn: the signal-plus-isosbestic pair on one
# fiber, with a pulse train on the first digital line and nothing on the second.
ONE_SITE_FILE_PATH = (
    OPHYS_DATA_PATH
    / "events_datasets"
    / "pyphotometry"
    / "narrow_pulses_and_idle_line"
    / "one_colour_time_division_window.ppd"
)
# A photodetector per excitation, so two fibers and two recording sites.
TWO_SITE_FILE_PATH = (
    OPHYS_DATA_PATH
    / "fiber_photometry_datasets"
    / "pyphotometry"
    / "mode_named_in_prose"
    / "two_colour_time_division.ppd"
)


def digital_line_onsets(file_path, digital_input):
    """The times a digital line goes low-to-high, which is what GuPPy records as its onsets."""
    (digital_signal,) = [
        signal for signal in _read_ppd(file_path).digital_signals if signal.digital_input == digital_input
    ]
    line = np.asarray(digital_signal.data)
    rising = np.flatnonzero((line[1:] > 0) & (line[:-1] == 0)) + 1
    return (digital_signal.starting_time_in_seconds + rising / digital_signal.rate_in_hz).tolist()


class TestGuppyConverterPyPhotometry:
    """A one-site session: the signal and its isosbestic control read off one photodetector."""

    RECORDING_SITE_TO_STORES = {"region": {"signal": "detector_1_excitation_1", "control": "detector_1_excitation_2"}}
    EVENT_STORE_TO_NAME = {"digital_1": "camera_frames", "digital_2": "port_entries"}

    @pytest.fixture(scope="class")
    @classmethod
    def acquisition_folder(cls, tmp_path_factory):
        folder_path = tmp_path_factory.mktemp("pyphotometry_session") / "session"
        folder_path.mkdir()
        shutil.copy(ONE_SITE_FILE_PATH, folder_path / ONE_SITE_FILE_PATH.name)
        return folder_path

    @pytest.fixture(scope="class")
    @classmethod
    def guppy_output_folder(cls, tmp_path_factory, acquisition_folder):
        file_path = acquisition_folder / ONE_SITE_FILE_PATH.name
        return generate_mock_guppy_output_folder(
            tmp_path_factory.mktemp("pyphotometry_output") / "session_output_1",
            recording_site_to_stores=cls.RECORDING_SITE_TO_STORES,
            event_store_to_name=cls.EVENT_STORE_TO_NAME,
            cross_correlation_pairs=(),
            event_onsets={
                "camera_frames": digital_line_onsets(file_path, digital_input=0),
                "port_entries": digital_line_onsets(file_path, digital_input=1),
            },
        )

    @pytest.fixture
    def converter(self, acquisition_folder, guppy_output_folder):
        return GuppyConverter(
            fiber_photometry_folder_path=acquisition_folder,
            events_folder_path=acquisition_folder,
            guppy_folder_path=guppy_output_folder,
            acquisition_format="pyphotometry",
        )

    @pytest.fixture
    def metadata(self, converter):
        recording_sites = list(self.RECORDING_SITE_TO_STORES)
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, build_device_metadata(recording_sites))
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_fiber_photometry_metadata(recording_sites)
        )
        metadata["FiberPhotometry"] = dict_deep_update(
            metadata["FiberPhotometry"], build_series_metadata(recording_sites)
        )
        return metadata

    def test_each_role_reads_its_store_as_its_stream(self, converter):
        """GuPPy's store id is the interface's stream name, so each role passes straight through."""
        for role, store_id in self.RECORDING_SITE_TO_STORES["region"].items():
            interface = converter.data_interface_objects[f"FiberPhotometry_{role}"]
            assert interface.stream_names == [store_id]

    def test_session_start_time_comes_from_the_ppd_header(self, converter):
        """Every header generation states ``date_time``, so the acquisition supplies the clock origin."""
        session_start_time = converter.get_metadata()["NWBFile"]["session_start_time"]
        assert session_start_time == datetime(2021, 6, 8, 16, 52, 48)

    def test_conversion(self, converter, metadata, tmp_path):
        """Both roles keep the board's stagger, and each line is written as GuPPy's onsets.

        The two excitations are strobed in turn on a 260 Hz timer, so the control trails the signal by
        one tick. GuPPy keeps a pulse's onset alone, so the lines are read as point events: 37 rising
        edges on ``digital_1`` and none on ``digital_2``, which still keeps its event type.
        """
        nwbfile_path = tmp_path / "pyphotometry.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True)

        nwbfile = read_nwb(str(nwbfile_path))
        try:
            assert nwbfile.acquisition["FiberPhotometryResponseSeriesSignal"].starting_time == 0.0
            assert nwbfile.acquisition["FiberPhotometryResponseSeriesControl"].starting_time == pytest.approx(1 / 260)

            camera_frames = nwbfile.get_events_table("CameraFrames")
            assert camera_frames.colnames == ("timestamp",)
            assert len(camera_frames) == 37
            np.testing.assert_allclose(
                camera_frames["timestamp"][:5], np.array([488, 493, 497, 501, 506]) / 130, rtol=1e-12
            )
            assert len(nwbfile.get_events_table("PortEntries")) == 0

            registry = nwbfile.processing["guppy"]["events"]
            registry_names = {str(registry["event_name"][row]) for row in range(len(registry.id))}
            assert registry_names == set(self.EVENT_STORE_TO_NAME.values())
        finally:
            nwbfile.read_io.close()


class TestPyPhotometryRefusals:
    """The two session shapes the pyPhotometry seam refuses rather than writes."""

    def test_a_role_spanning_two_recording_sites_raises(self, tmp_path):
        """Two fibers are two slots sampled at different instants, which no one series can hold."""
        acquisition_folder = tmp_path / "session"
        acquisition_folder.mkdir()
        shutil.copy(TWO_SITE_FILE_PATH, acquisition_folder / TWO_SITE_FILE_PATH.name)

        with pytest.raises(AssertionError, match="cannot be written as one series"):
            build_pyphotometry_acquisition_interface(
                folder_path=acquisition_folder,
                store_ids=["detector_1_excitation_1", "detector_2_excitation_2"],
                metadata_key="signal",
                verbose=False,
            )

    def test_multiple_ppd_files_raise(self, tmp_path):
        """A GuPPy pyPhotometry session folder holds exactly one recording."""
        acquisition_folder = tmp_path / "session"
        acquisition_folder.mkdir()
        for file_path in (ONE_SITE_FILE_PATH, TWO_SITE_FILE_PATH):
            shutil.copy(file_path, acquisition_folder / file_path.name)

        with pytest.raises(AssertionError, match="Expected exactly one pyPhotometry '.ppd' file"):
            resolve_ppd_file(Path(acquisition_folder))
