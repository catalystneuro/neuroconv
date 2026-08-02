"""Old-shaped metadata still produces the file the user asked for, ecephys.

The contract these tests hold NeuroConv to: a script that passes list-based metadata gets the values it
stated written to the file, whatever NeuroConv does internally. That is the whole of what "the old format
is still supported" means, so it is asserted directly rather than inferred from the writers.

They exist because nothing else exercises it any more. NeuroConv fills its own metadata with the dict-based
format and the shared test mixins ask every interface for that format too, so no other test in the suite
converts from list-based metadata. Without this module the old format would be shipping code that nothing
runs, which is worse than not supporting it.

The assertions are about values the caller stated, a named and described device, per-group descriptions and
locations, a series name, rather than about defaults. The failure they are built to catch is not the old
writer computing something wrong; it is the format dispatch quietly sending old metadata down the dict path,
where those edits are ignored and defaults are written in their place.

They outlive the old writers. When old metadata is translated at the boundary of ``add_to_nwbfile`` and the
``_old_list_format`` writers are deleted, these assertions do not change: they become the proof that
translation preserves what the user stated. Delete this module only when the old shape stops being accepted
at all, together with ``use_new_metadata_format``.
"""

from datetime import datetime

import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import MockRecordingInterface


class TestOldMetadataCompatibilityEcephys:
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
