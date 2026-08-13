import pytest
from pynwb import read_nwb

from neuroconv.converters import ScanImageConverter
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH

SCANIMAGE_FOLDER_PATH = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"


class TestScanImageConverterPlanarTwoChannels:
    """Two channels of a planar acquisition: one TwoPhotonSeries and one ImagingPlane each."""

    file_path = SCANIMAGE_FOLDER_PATH / "planar_two_channels_single_file" / "planar_two_ch_single_files_00001_00001.tif"

    def test_run_conversion(self, tmp_path):
        converter = ScanImageConverter(file_path=self.file_path)

        assert list(converter.data_interface_objects) == [
            "ScanImageImaging_Channel_1",
            "ScanImageImaging_Channel_2",
        ]

        nwbfile_path = str(tmp_path / "scanimage_planar_two_channels.nwb")
        metadata = converter.get_metadata()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        # Each channel is its own series, addressed by position in the old list-based metadata.
        assert set(nwbfile.acquisition) == {"TwoPhotonSeriesChannel1", "TwoPhotonSeriesChannel2"}
        assert set(nwbfile.imaging_planes) == {"ImagingPlaneChannel1", "ImagingPlaneChannel2"}
        # One microscope for the acquisition, shared by both channels.
        assert len(nwbfile.devices) == 1
        assert nwbfile.acquisition["TwoPhotonSeriesChannel1"].data.shape[1:] == (20, 20)


class TestScanImageConverterVolumetricTwoChannels:
    """A volumetric acquisition writes one 4D series per channel."""

    file_path = SCANIMAGE_FOLDER_PATH / "volumetric_two_channels_single_file" / "vol_two_ch_single_file_00001_00001.tif"

    def test_run_conversion(self, tmp_path):
        converter = ScanImageConverter(file_path=self.file_path)

        nwbfile_path = str(tmp_path / "scanimage_volumetric_two_channels.nwb")
        metadata = converter.get_metadata()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert set(nwbfile.acquisition) == {"TwoPhotonSeriesChannel1", "TwoPhotonSeriesChannel2"}
        for series_name in nwbfile.acquisition:
            # (samples, height, width, planes), the volume kept together.
            assert nwbfile.acquisition[series_name].data.shape[1:] == (20, 20, 9)


class TestScanImageConverterSingleChannel:
    """A single-channel acquisition needs no arguments and carries no channel suffix."""

    file_path = (
        SCANIMAGE_FOLDER_PATH / "volumetric_single_channel_single_file" / "vol_one_ch_single_files_00002_00001.tif"
    )

    def test_run_conversion(self, tmp_path):
        converter = ScanImageConverter(file_path=self.file_path)

        assert list(converter.data_interface_objects) == ["ScanImageImaging"]

        nwbfile_path = str(tmp_path / "scanimage_single_channel.nwb")
        metadata = converter.get_metadata()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        nwbfile = read_nwb(nwbfile_path)
        assert len(nwbfile.acquisition) == 1


class TestScanImageConverterMultiFile:
    """A multi-file acquisition is followed from its first file, for every channel."""

    file_path = SCANIMAGE_FOLDER_PATH / "volumetric_two_channels_multi_file" / "vol_two_ch_multi_files_00001_00001.tif"

    def test_files_are_followed_for_every_channel(self):
        converter = ScanImageConverter(file_path=self.file_path)

        assert list(converter.data_interface_objects) == [
            "ScanImageImaging_Channel_1",
            "ScanImageImaging_Channel_2",
        ]
        num_samples_per_channel = {
            name: interface.imaging_extractor.get_num_samples()
            for name, interface in converter.data_interface_objects.items()
        }
        # The ten files of the series reach both channels, not just the one the first file starts.
        assert len(set(num_samples_per_channel.values())) == 1
        assert next(iter(num_samples_per_channel.values())) > 1


class TestScanImageConverterSourceValidation:
    def test_no_file_raises(self):
        with pytest.raises(ValueError, match="Either 'file_path' or 'file_paths' must be provided."):
            ScanImageConverter()
