import sys
import tempfile
import unittest
import numpy as np
from pathlib import Path

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
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhd_test_1.rhd")),
                ),
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(Path.cwd() / "ephy_testing_data" / "intan" / "intan_rhs_test_1.rhs")),
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
            converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)
            recording = converter.data_interface_objects["TestRecording"].recording_extractor
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            if np.all(recording.get_channel_offsets() == 0):
                check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
                check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)
            else:
                new_dtype = recording.get_dtype(return_scaled=False).name[1:]
                traces_1 = recording.get_traces(return_scaled=False).astype(new_dtype)
                unsigned_coercion = (recording.get_channel_offsets() / recording.get_channel_gains()).astype(new_dtype)
                for j, x in enumerate(unsigned_coercion):
                    traces_1[j, :] -= x
                scaled_traces_2 = nwb_recording.get_traces(return_scaled=True)
                for j, x in enumerate(nwb_recording.get_channel_offsets()):
                    scaled_traces_2[j, :] -= x
                np.testing.assert_almost_equal(traces_1, nwb_recording.get_traces(return_scaled=False))
                np.testing.assert_almost_equal(recording.get_traces(return_scaled=True), scaled_traces_2)


if __name__ == "__main__":
    unittest.main()
