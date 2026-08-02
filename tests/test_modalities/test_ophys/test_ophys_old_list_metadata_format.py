"""Coverage for the old list-based metadata format on the ophys write path.

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

from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


class TestOldListMetadataFormatImaging:
    """Write files from list-based `Ophys` metadata the way a user's script still has it."""

    @pytest.fixture
    def interface(self):
        return MockImagingInterface()

    def _old_format_metadata(self, interface) -> dict:
        """The metadata a user has after editing what `get_metadata()` hands them."""
        metadata = interface.get_metadata()
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

    def test_get_metadata_still_returns_the_list_format(self, interface):
        """The promise the internal default flip makes: what users get back is unchanged."""
        metadata = interface.get_metadata()

        assert isinstance(metadata["Ophys"]["Device"], list)
        assert isinstance(metadata["Ophys"]["ImagingPlane"], list)
        assert isinstance(metadata["Ophys"]["TwoPhotonSeries"], list)
        assert "Devices" not in metadata
        assert "MicroscopySeries" not in metadata["Ophys"]

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


class TestOldListMetadataFormatSegmentation:
    """The segmentation writers read plane segmentations from a list in the old format."""

    @pytest.fixture
    def interface(self):
        return MockSegmentationInterface()

    def _old_format_metadata(self, interface) -> dict:
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0).astimezone())
        metadata["Ophys"]["Device"] = [dict(name="MyMicroscope", description="A microscope I described")]
        metadata["Ophys"]["ImagingPlane"][0].update(device="MyMicroscope", location="CA1")
        plane_segmentations = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"]
        plane_segmentations[0].update(description="The ROIs I described")
        return metadata

    def test_get_metadata_still_returns_the_list_format(self, interface):
        metadata = interface.get_metadata()

        assert isinstance(metadata["Ophys"]["Device"], list)
        assert isinstance(metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"], list)
        assert "PlaneSegmentations" not in metadata["Ophys"]

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
