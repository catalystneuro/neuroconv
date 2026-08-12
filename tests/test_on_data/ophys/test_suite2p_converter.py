import shutil
from datetime import datetime

import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import Suite2pConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH

SUITE2P_FOLDER_PATH = OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"


class TestSuite2pConverter:
    """The whole folder: two planes by two channels, written in one call."""

    def test_run_conversion(self, tmp_path):
        converter = Suite2pConverter(folder_path=str(SUITE2P_FOLDER_PATH))

        assert list(converter.data_interface_objects) == [
            "Suite2pSegmentation_chan1_plane0",
            "Suite2pSegmentation_chan2_plane0",
            "Suite2pSegmentation_chan1_plane1",
            "Suite2pSegmentation_chan2_plane1",
        ]

        nwbfile_path = str(tmp_path / "suite2p_all_planes_and_channels.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_description="test", session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            plane_segmentations = nwbfile.processing["ophys"]["ImageSegmentation"].plane_segmentations
            assert set(plane_segmentations) == {
                "PlaneSegmentationChan1Plane0",
                "PlaneSegmentationChan2Plane0",
                "PlaneSegmentationChan1Plane1",
                "PlaneSegmentationChan2Plane1",
            }
            # One ImagingPlane per (channel, plane) pair, see the 'one ImagingPlane per channel' policy.
            assert set(nwbfile.imaging_planes) == {
                "ImagingPlaneChan1Plane0",
                "ImagingPlaneChan2Plane0",
                "ImagingPlaneChan1Plane1",
                "ImagingPlaneChan2Plane1",
            }
            assert set(nwbfile.processing["ophys"]["Fluorescence"].roi_response_series) == {
                "RoiResponseSeriesChan1Plane0",
                "NeuropilChan1Plane0",
                "DeconvolvedChan1Plane0",
                "RoiResponseSeriesChan2Plane0",
                "NeuropilChan2Plane0",
                "RoiResponseSeriesChan1Plane1",
                "NeuropilChan1Plane1",
                "DeconvolvedChan1Plane1",
                "RoiResponseSeriesChan2Plane1",
                "NeuropilChan2Plane1",
            }

    def test_combined_folder_is_skipped(self):
        """Suite2p writes a 'combined' folder whose ROIs repeat the per-plane ones."""
        converter = Suite2pConverter(folder_path=str(SUITE2P_FOLDER_PATH))

        assert (SUITE2P_FOLDER_PATH / "combined").is_dir()
        assert not any("combined" in name for name in converter.data_interface_objects)


class TestSuite2pConverterSinglePlaneSingleChannel:
    """The commonest Suite2p session: one plane, one channel, nothing to disambiguate."""

    @pytest.fixture
    def folder_path(self, tmp_path):
        folder_path = tmp_path / "suite2p"
        shutil.copytree(SUITE2P_FOLDER_PATH / "plane0", folder_path / "plane0")
        (folder_path / "plane0" / "F_chan2.npy").unlink()
        (folder_path / "plane0" / "Fneu_chan2.npy").unlink()
        return folder_path

    def test_run_conversion(self, folder_path, tmp_path):
        converter = Suite2pConverter(folder_path=str(folder_path))

        assert list(converter.data_interface_objects) == ["Suite2pSegmentation_chan1_plane0"]

        nwbfile_path = str(tmp_path / "suite2p_single_plane_single_channel.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_description="test", session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            # With nothing to disambiguate the names carry no channel or plane suffix.
            assert list(nwbfile.processing["ophys"]["ImageSegmentation"].plane_segmentations) == ["PlaneSegmentation"]
            assert list(nwbfile.imaging_planes) == ["ImagingPlane"]


class TestSuite2pConverterChannelInOnePlaneOnly:
    """A second channel segmented for some planes but not others."""

    @pytest.fixture
    def folder_path(self, tmp_path):
        folder_path = tmp_path / "suite2p"
        shutil.copytree(SUITE2P_FOLDER_PATH, folder_path)
        (folder_path / "plane1" / "F_chan2.npy").unlink()
        (folder_path / "plane1" / "Fneu_chan2.npy").unlink()
        return folder_path

    def test_plane_without_the_channel_is_skipped(self, folder_path, tmp_path):
        """The extractor reports the channels of the first plane for the whole folder, so building the
        full cross product would reach for trace files that plane1 does not have."""
        converter = Suite2pConverter(folder_path=str(folder_path))

        assert list(converter.data_interface_objects) == [
            "Suite2pSegmentation_chan1_plane0",
            "Suite2pSegmentation_chan2_plane0",
            "Suite2pSegmentation_chan1_plane1",
        ]

        nwbfile_path = str(tmp_path / "suite2p_one_plane_without_chan2.nwb")
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_description="test", session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            assert set(nwbfile.processing["ophys"]["ImageSegmentation"].plane_segmentations) == {
                "PlaneSegmentationChan1Plane0",
                "PlaneSegmentationChan2Plane0",
                "PlaneSegmentationChan1Plane1",
            }
