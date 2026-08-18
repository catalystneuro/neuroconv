import platform
import sys
from datetime import datetime, timezone

import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import InscopixGpioInterface
from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH


# `isx`, which reads the file, resolves on neither of these, so the tests below have nothing to read.
# Mirrors the guards on the other Inscopix classes in `test_imaging_interfaces.py` and
# `test_segmentation_interfaces.py`, and the equivalent skip the gallery conftest applies to the page.
skip_on_darwin_arm64 = pytest.mark.skipif(
    platform.system() == "Darwin" and platform.machine() == "arm64",
    reason="The isx package is currently not natively supported on macOS with Apple Silicon. "
    "Installation instructions can be found at: "
    "https://github.com/inscopix/pyisx?tab=readme-ov-file#install",
)
skip_on_python_313 = pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="Tests are skipped on Python 3.13 because of incompatibility with the 'isx' module "
    "Requires: Python <3.13, >=3.9)"
    "See:https://github.com/inscopix/pyisx/issues",
)


@skip_on_darwin_arm64
@skip_on_python_313
class TestInscopixGpioOdorConcentrationStimulus:
    """InscopixGpioInterface writes every channel of an Inscopix ``.gpio`` file as a ``TimeSeries``.

    ``odor_concentration_stimulus.gpio`` holds 26 channels sampled irregularly: four monitor channels
    with known units, general-purpose GPIO inputs, digital lines and BNC sync. ``GPIO-2`` is the odor
    code, 336 samples spanning the four levels 128, 144, 160 and 224.
    """

    FILE_PATH = str(OPHYS_DATA_PATH / "analog_datasets" / "inscopix" / "gpio" / "odor_concentration_stimulus.gpio")

    # Monitor channels have known units; everything else defaults to "a.u.".
    MONITOR_UNITS = {
        "EX-LED": "mW/mm^2",
        "OG-LED": "mW/mm^2",
        "DI-LED": "mW/mm^2",
        "e-focus": "micrometers",
    }

    def test_get_metadata(self):
        interface = InscopixGpioInterface(file_path=self.FILE_PATH)

        metadata = interface.get_metadata()

        assert metadata["NWBFile"]["session_start_time"] == datetime(
            2025, 2, 27, 11, 25, 28, 935000, tzinfo=timezone.utc
        )

        # One entry per channel, keyed by the interface and the channel it describes.
        time_series_metadata = metadata["TimeSeries"]
        assert len(time_series_metadata) == 26
        assert time_series_metadata["inscopix_gpio_gpio_1"] == {
            "name": "GPIO-1",
            "description": "Inscopix GPIO channel 'GPIO-1'.",
        }
        # The monitor channels are the only ones whose unit the format fixes; the rest state none, so
        # nothing here claims a unit the file did not record.
        assert time_series_metadata["inscopix_gpio_e_focus"]["unit"] == "micrometers"
        assert "unit" not in time_series_metadata["inscopix_gpio_gpio_1"]

    def test_get_available_channels(self):
        inventory = InscopixGpioInterface.get_available_channels(self.FILE_PATH)
        assert len(inventory) == 26
        by_name = {entry["name"]: entry for entry in inventory}
        # GPIO-2 is the odor code: 336 samples spanning four levels.
        assert by_name["GPIO-2"]["num_samples"] == 336
        assert by_name["GPIO-2"]["unique_values"] == [128.0, 144.0, 160.0, 224.0]

    def test_add_to_nwbfile(self, tmp_path):
        interface = InscopixGpioInterface(file_path=self.FILE_PATH)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        nwbfile_path = tmp_path / "test_inscopix_gpio.nwb"
        configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")
        read_nwbfile = read_nwb(path=nwbfile_path)

        # Every one of the 26 channels is written as a TimeSeries (digital and BNC lines included).
        assert len(read_nwbfile.acquisition) == 26
        assert "BNC_Sync_Output" in read_nwbfile.acquisition
        assert "Digital_GPI_0" in read_nwbfile.acquisition
        assert read_nwbfile.acquisition["GPIO-2"].data.shape[0] == 336
        for name, unit in self.MONITOR_UNITS.items():
            time_series = read_nwbfile.acquisition[name]
            assert time_series.unit == unit
            # Irregular sampling: explicit per-event timestamps, not a fixed rate.
            assert time_series.timestamps is not None
            assert time_series.rate is None
        # A general-purpose GPIO input has no known unit.
        assert read_nwbfile.acquisition["GPIO-1"].unit == "a.u."

    def test_exclude_channels(self):
        nwbfile = mock_NWBFile()
        interface = InscopixGpioInterface(
            file_path=self.FILE_PATH, exclude_channels=["BNC Sync Output", "Digital GPI 0"]
        )
        interface.add_to_nwbfile(nwbfile=nwbfile)
        assert len(nwbfile.acquisition) == 24
        assert "BNC_Sync_Output" not in nwbfile.acquisition
        assert "Digital_GPI_0" not in nwbfile.acquisition
        # The dropped channels are absent from the metadata too, so nothing seeds an unwritten object.
        assert len(interface.get_metadata()["TimeSeries"]) == 24

    def test_the_unit_and_conversion_are_edited_in_the_metadata(self):
        interface = InscopixGpioInterface(file_path=self.FILE_PATH)
        metadata = interface.get_metadata()
        metadata["TimeSeries"]["inscopix_gpio_gpio_1"].update(unit="volts", conversion=2.5)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert nwbfile.acquisition["GPIO-1"].unit == "volts"
        assert nwbfile.acquisition["GPIO-1"].conversion == 2.5
        assert nwbfile.acquisition["e-focus"].unit == "micrometers"
        assert nwbfile.acquisition["e-focus"].conversion == 1.0

    def test_stub_test_truncates(self):
        interface = InscopixGpioInterface(file_path=self.FILE_PATH)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, stub_test=True)
        # GPIO-1 has 475 samples in full; stub_test writes at most 100.
        assert nwbfile.acquisition["GPIO-1"].data.shape[0] == 100
