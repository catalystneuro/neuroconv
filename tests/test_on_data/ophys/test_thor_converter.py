from pynwb import read_nwb

from neuroconv.converters import ThorConverter
from neuroconv.datainterfaces import ThorImagingInterface
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH

THORLABS_FOLDER_PATH = OPHYS_DATA_PATH / "imaging_datasets" / "ThorlabsTiff"


class TestThorConverterSingleChannel:
    """A single-channel acquisition writes the same file the interface writes on its own."""

    file_path = THORLABS_FOLDER_PATH / "single_channel_single_plane" / "20231018-002" / "ChanA_001_001_001_001.tif"

    def test_run_conversion(self, tmp_path):
        converter = ThorConverter(file_path=self.file_path)

        assert list(converter.data_interface_objects) == ["ThorImaging"]

        nwbfile_path = str(tmp_path / "thor_converter.nwb")
        metadata = converter.get_metadata()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        interface = ThorImagingInterface(file_path=self.file_path)
        interface_nwbfile_path = str(tmp_path / "thor_interface.nwb")
        interface_metadata = interface.get_metadata()
        interface.run_conversion(nwbfile_path=interface_nwbfile_path, overwrite=True, metadata=interface_metadata)

        nwbfile = read_nwb(nwbfile_path)
        interface_nwbfile = read_nwb(interface_nwbfile_path)
        # The converter names nothing after the single channel, so the two files agree.
        assert set(nwbfile.acquisition) == set(interface_nwbfile.acquisition)
        assert set(nwbfile.imaging_planes) == set(interface_nwbfile.imaging_planes)
        assert set(nwbfile.devices) == set(interface_nwbfile.devices) == {"ThorMicroscope"}

    def test_square_field_of_view_keeps_both_of_its_values(self, tmp_path):
        """The acquisition is 512 by 512, so its field of view and grid spacing repeat a value.

        Merging the interfaces' metadata by appending lists would dedupe those two equal values into
        one, and NWB requires two or three.
        """
        converter = ThorConverter(file_path=self.file_path)

        metadata = converter.get_metadata()
        series_metadata = metadata["Ophys"]["MicroscopySeries"]["thor_imaging"]
        imaging_plane_metadata = metadata["Ophys"]["ImagingPlanes"]["thor_imaging"]
        assert len(series_metadata["field_of_view"]) == 2
        assert len(imaging_plane_metadata["grid_spacing"]) == 2

        nwbfile_path = str(tmp_path / "thor_square_field_of_view.nwb")
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.acquisition["TwoPhotonSeriesDefault"].field_of_view) == 2


class TestThorConverterMultiChannel:
    """Two channels over three z planes, written in one call."""

    file_path = THORLABS_FOLDER_PATH / "multi_channel_multi_plane" / "lzw_compressed" / "ChanA_0001_0001_0001_0001.tif"

    def test_get_available_channels(self):
        channel_names = ThorConverter.get_available_channels(file_path=self.file_path)

        assert channel_names == ["ChanA", "ChanB"]
        # The names are what the interface accepts back, which is the point of asking.
        ThorImagingInterface(file_path=self.file_path, channel_name=channel_names[0])

    def test_run_conversion(self, tmp_path):
        converter = ThorConverter(file_path=self.file_path)

        assert list(converter.data_interface_objects) == ["ThorImaging_ChanA", "ThorImaging_ChanB"]

        nwbfile_path = str(tmp_path / "thor_multi_channel.nwb")
        metadata = converter.get_metadata()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert set(nwbfile.acquisition) == {"TwoPhotonSeriesChanA", "TwoPhotonSeriesChanB"}
        # One ImagingPlane per channel, see the 'one ImagingPlane per channel' policy.
        assert set(nwbfile.imaging_planes) == {"ImagingPlaneChanA", "ImagingPlaneChanB"}
        # One microscope for the acquisition, shared by both channels.
        assert set(nwbfile.devices) == {"ThorMicroscope"}
        for series_name in nwbfile.acquisition:
            # (samples, height, width, planes): three timepoints of a three-plane volume.
            assert nwbfile.acquisition[series_name].data.shape == (3, 128, 128, 3)
