"""Old-shaped metadata still produces the file the user asked for, ophys.

The contract these tests hold NeuroConv to: a script that passes list-based metadata gets the values it
stated written to the file, whatever NeuroConv does internally. That is the whole of what "the old format
is still supported" means, so it is asserted directly rather than inferred from the writers.

They exist because nothing else exercises it any more. NeuroConv fills its own metadata with the dict-based
format and the shared test mixins ask every interface for that format too, so no other test in the suite
converts from list-based metadata. Without this module the old format would be shipping code that nothing
runs, which is worse than not supporting it.

The assertions are about values the caller stated, a named and described microscope, an imaging plane with its
indicator and location, a renamed series, rather than about defaults. The failure they are built to catch is not the old
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

from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


class TestOldMetadataCompatibilityImaging:
    """Write files from list-based `Ophys` metadata the way a user's script still has it."""

    @pytest.fixture
    def interface(self):
        return MockImagingInterface()

    def _old_format_metadata(self, interface) -> dict:
        """The metadata a user has after editing what `get_metadata()` hands them.

        The format is asked for explicitly rather than taken from the default, so this keeps building
        old-shaped metadata when the default flips.
        """
        metadata = interface.get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0).astimezone())
        metadata["Ophys"]["Device"] = [dict(name="MyMicroscope", description="A microscope I described")]
        metadata["Ophys"]["ImagingPlane"][0].update(
            name="ImagingPlaneGreen",
            description="The plane I described",
            excitation_lambda=488.0,
            indicator="GCaMP6f",
            location="CA1",
            device="MyMicroscope",
        )
        metadata["Ophys"]["TwoPhotonSeries"][0].update(
            name="TwoPhotonSeriesGreen",
            description="The series I described",
            imaging_plane="ImagingPlaneGreen",
        )
        return metadata

    def test_run_conversion_writes_what_the_user_stated(self, interface, tmp_path):
        metadata = self._old_format_metadata(interface)
        nwbfile_path = tmp_path / "old_list_format_imaging.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        # No placeholder device alongside the stated one: the old path claimed it, the dict path would
        # have ignored these entries and written its own.
        assert list(nwbfile.devices) == ["MyMicroscope"]
        assert nwbfile.devices["MyMicroscope"].description == "A microscope I described"

        imaging_plane = nwbfile.imaging_planes["ImagingPlaneGreen"]
        assert imaging_plane.indicator == "GCaMP6f"
        assert imaging_plane.location == "CA1"
        assert imaging_plane.device.name == "MyMicroscope"

        photon_series = nwbfile.acquisition["TwoPhotonSeriesGreen"]
        assert photon_series.description == "The series I described"
        assert photon_series.imaging_plane.name == "ImagingPlaneGreen"

    def test_add_to_nwbfile_writes_what_the_user_stated(self, interface):
        """The `run_conversion` path validates the metadata; this one does not, and dispatches alone."""
        metadata = self._old_format_metadata(interface)
        nwbfile = mock_NWBFile()

        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert list(nwbfile.devices) == ["MyMicroscope"]
        assert "ImagingPlaneGreen" in nwbfile.imaging_planes
        assert "TwoPhotonSeriesGreen" in nwbfile.acquisition


class TestOldMetadataCompatibilitySegmentation:
    """The segmentation writers read plane segmentations from a list in the old format."""

    @pytest.fixture
    def interface(self):
        return MockSegmentationInterface()

    def _old_format_metadata(self, interface) -> dict:
        """Old-shaped metadata, asked for explicitly so it survives the default flipping."""
        metadata = interface.get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0).astimezone())
        metadata["Ophys"]["Device"] = [dict(name="MyMicroscope", description="A microscope I described")]
        metadata["Ophys"]["ImagingPlane"][0].update(device="MyMicroscope", location="CA1")
        plane_segmentations = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"]
        plane_segmentations[0].update(description="The ROIs I described")
        return metadata

    def test_run_conversion_writes_what_the_user_stated(self, interface, tmp_path):
        metadata = self._old_format_metadata(interface)
        nwbfile_path = tmp_path / "old_list_format_segmentation.nwb"

        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        assert list(nwbfile.devices) == ["MyMicroscope"]
        assert nwbfile.imaging_planes["ImagingPlane"].location == "CA1"

        image_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]
        plane_segmentation = image_segmentation.plane_segmentations["PlaneSegmentation"]
        assert plane_segmentation.description == "The ROIs I described"
        assert plane_segmentation.imaging_plane.name == "ImagingPlane"

    def test_an_extractor_with_no_traces_still_converts(self):
        # The old defaults declare six trace roles on every segmentation, so translated metadata asks for
        # traces from extractors that have none (`InscopixSegmentationInterface` among them). The dict
        # writer rejects a request it cannot satisfy, which is right for metadata someone wrote and wrong
        # for boilerplate, so the translated block is dropped and the conversion writes nothing for it,
        # which is what the old writer did.
        interface = MockSegmentationInterface(
            has_raw_signal=False, has_dff_signal=False, has_deconvolved_signal=False, has_neuropil_signal=False
        )
        metadata = interface.get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1).astimezone())

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert "Fluorescence" not in nwbfile.processing["ophys"].data_interfaces
        assert "ImageSegmentation" in nwbfile.processing["ophys"].data_interfaces
