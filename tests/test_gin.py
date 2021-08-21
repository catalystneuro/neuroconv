import tempfile
import unittest
from pathlib import Path
import sys

from spikeextractors import NwbRecordingExtractor
from spikeextractors.testing import check_recordings_equal
from nwb_conversion_tools import (
    NWBConverter,
    IntanRecordingInterface,
)

try:
    from datalad.api import install, Dataset
    from parameterized import parameterized

    HAVE_DATALAD = True
except ImportError:
    HAVE_DATALAD = False

if HAVE_DATALAD and sys.platform == "linux":

    class TestNwbConversions(unittest.TestCase):
        def setUp(self):
            pt = Path.cwd() / "ephy_testing_data"
            if pt.exists():
                self.dataset = Dataset(pt)
            else:
                self.dataset = install("https://gin.g-node.org/NeuralEnsemble/ephy_testing_data")
            self.savedir = Path(tempfile.mkdtemp())

        @parameterized.expand(
            [
                dict(
                    recording_interface=IntanRecordingInterface,
                    dataset_path="intan",
                    interface_kwargs=dict(
                        file_path=str(Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhd_test_1.rhd")
                    ),
                ),
                dict(
                    recording_interface=IntanRecordingInterface,
                    dataset_path="intan",
                    interface_kwargs=dict(
                        file_path=str(Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhs_test_1.rhs")
                    ),
                ),
            ]
        )
        def test_convert_recording_extractor_to_nwb(self, recording_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {recording_interface.__name__}...")
            dataset_stem = Path(dataset_path).stem
            self.dataset.get(dataset_path)
            nwbfile_path = self.savedir / f"{recording_interface.__name__}_test_{dataset_stem}.nwb"

            class TestConverter(NWBConverter):
                data_interface_classes = dict(TestRecording=recording_interface)

            converter = TestConverter(source_data=dict(TestRecording=dict(interface_kwargs)))
            converter.run_conversion(nwbfile_path=nwbfile_path)
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            check_recordings_equal(
                RX1=converter.data_interface_objects["TestRecording"].recording_extractor,
                RX2=nwb_recording,
                check_times=False,
            )


if __name__ == "__main__":
    unittest.main()
