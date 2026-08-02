"""Coverage for the old list-based metadata format on the ecephys write path.

NeuroConv fills its own metadata with the dict-based format, and the test mixins ask every interface for
that format too, so nothing else in the suite writes a file from list-based metadata. The format is still
supported for users who pass their own, which is what these tests keep exercising: not only that the old
writers produce the right objects, but that the format dispatch still routes list-shaped metadata to them
now that dict is what everything else uses.

Delete this module together with the old list-based format.
"""

from datetime import datetime

import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


class TestOldListMetadataFormatEcephys:
    """Write files from list-based `Ecephys` metadata the way a user's script still has it."""

    @pytest.fixture
    def interface(self):
        interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        interface.recording_extractor.set_property(key="group_name", values=["s1", "s1", "s2", "s2"])
        return interface

    def _old_format_metadata(self, interface) -> dict:
        """The metadata a user has after editing what `get_metadata()` hands them."""
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0).astimezone())
        metadata["Ecephys"]["Device"] = [dict(name="MyAcquisitionSystem", description="A system I described")]
        metadata["Ecephys"]["ElectrodeGroup"] = [
            dict(name="s1", description="Shank 1", location="CA1", device="MyAcquisitionSystem"),
            dict(name="s2", description="Shank 2", location="CA3", device="MyAcquisitionSystem"),
        ]
        metadata["Ecephys"]["ElectricalSeries"] = dict(name="ElectricalSeriesRaw", description="Raw traces I described")
        return metadata

    def test_get_metadata_still_returns_the_list_format(self, interface):
        """The promise the internal default flip makes: what users get back is unchanged."""
        metadata = interface.get_metadata()

        assert isinstance(metadata["Ecephys"]["Device"], list)
        assert isinstance(metadata["Ecephys"]["ElectrodeGroup"], list)
        assert set(metadata["Ecephys"]["ElectricalSeries"]) == {"name", "description"}
        assert "Devices" not in metadata
        assert "ElectrodeGroups" not in metadata["Ecephys"]

    def test_run_conversion_writes_what_the_user_stated(self, interface, tmp_path):
        metadata = self._old_format_metadata(interface)
        nwbfile_path = tmp_path / "old_list_format_ecephys.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        # No placeholder device alongside the stated one: the old path claimed it, the dict path would
        # have ignored these entries and written its own.
        assert list(nwbfile.devices) == ["MyAcquisitionSystem"]
        assert nwbfile.devices["MyAcquisitionSystem"].description == "A system I described"

        assert set(nwbfile.electrode_groups) == {"s1", "s2"}
        assert nwbfile.electrode_groups["s1"].description == "Shank 1"
        assert nwbfile.electrode_groups["s1"].location == "CA1"
        assert nwbfile.electrode_groups["s2"].location == "CA3"
        assert nwbfile.electrode_groups["s2"].device.name == "MyAcquisitionSystem"

        electrical_series = nwbfile.acquisition["ElectricalSeriesRaw"]
        assert electrical_series.description == "Raw traces I described"

    def test_add_to_nwbfile_writes_what_the_user_stated(self, interface):
        """The `run_conversion` path validates the metadata; this one does not, and dispatches alone."""
        metadata = self._old_format_metadata(interface)
        nwbfile = mock_NWBFile()

        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert list(nwbfile.devices) == ["MyAcquisitionSystem"]
        assert nwbfile.electrode_groups["s1"].description == "Shank 1"
        assert "ElectricalSeriesRaw" in nwbfile.acquisition

    def test_run_conversion_through_a_converter(self, interface, tmp_path):
        """A converter merges its interfaces' metadata, so it is where the shape is easiest to lose."""
        converter = ConverterPipe(data_interfaces=dict(Recording=interface))

        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0).astimezone())
        metadata["Ecephys"]["Device"] = [dict(name="MyAcquisitionSystem", description="A system I described")]
        metadata["Ecephys"]["ElectrodeGroup"] = [
            dict(name="s1", description="Shank 1", location="CA1", device="MyAcquisitionSystem"),
            dict(name="s2", description="Shank 2", location="CA3", device="MyAcquisitionSystem"),
        ]

        nwbfile_path = tmp_path / "old_list_format_ecephys_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        assert list(nwbfile.devices) == ["MyAcquisitionSystem"]
        assert nwbfile.electrode_groups["s2"].location == "CA3"
