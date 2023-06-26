from datetime import datetime
from unittest import TestCase

from pynwb import NWBHDF5IO
from pynwb.image import ImageSeries
from pynwb.ophys import OnePhotonSeries

from neuroconv.converters import MiniscopeConverterPipe
from neuroconv.tools.testing.converter_pipe_mixins import ConverterPipeTestMixin
from tests.test_on_data.setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


class TestMiniscopeConverter(ConverterPipeTestMixin, TestCase):
    converter_cls = MiniscopeConverterPipe
    converter_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        metadata = self.converter.get_metadata()
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2021, 10, 7, 15, 3, 28, 635),
        )

    def check_read_nwb(self, nwbfile_path: str):
        metadata = self.converter.get_metadata()
        device_name = metadata["Ophys"]["Device"][0]["name"]
        behavcam_device_name = metadata["Behavior"]["Device"][0]["name"]
        photon_series_name = metadata["Ophys"]["OnePhotonSeries"][0]["name"]
        image_series_name = metadata["Behavior"]["ImageSeries"][0]["name"]

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            self.assertEqual(
                nwbfile.session_start_time,
                datetime(2021, 10, 7, 15, 3, 28, 635).astimezone(),
            )

            self.assertIn(device_name, nwbfile.devices)
            self.assertIn(behavcam_device_name, nwbfile.devices)
            self.assertIn(photon_series_name, nwbfile.acquisition)
            self.assertIsInstance(nwbfile.acquisition[photon_series_name], OnePhotonSeries)
            self.assertIn(image_series_name, nwbfile.acquisition)
            self.assertIsInstance(nwbfile.acquisition[image_series_name], ImageSeries)
