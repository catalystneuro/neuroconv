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
    from datalad.api import install

    HAVE_DATALAD = True
except ImportError:
    HAVE_DATALAD = False

try:
    from parameterized import parameterized

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

RUN_LOCAL = True
LOCAL_PATH = Path("D:/GIN")  # Path to dataset downloaded from https://gin.g-node.org/NeuralEnsemble/ephy_testing_data


if HAVE_PARAMETERIZED and (HAVE_DATALAD and sys.platform == "linux" or RUN_LOCAL):

    class TestNwbConversions(unittest.TestCase):
        dataset = None
        savedir = Path(tempfile.mkdtemp())

        if RUN_LOCAL and LOCAL_PATH.exists():
            data_path = LOCAL_PATH
        else:
            data_path = Path.cwd() / "ephy_testing_data"

        def setUp(self):
            if RUN_LOCAL:
                if not self.data_path.exists():
                    if HAVE_DATALAD:
                        self.dataset = install("https://gin.g-node.org/NeuralEnsemble/ephy_testing_data")
                    else:
                        raise OSError(f"The manually specified data path ({self.data_path}) does not exist!")
            else:
                self.dataset = install("https://gin.g-node.org/NeuralEnsemble/ephy_testing_data")

        @parameterized.expand(
            [
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(data_path / "intan" / "intan_rhd_test_1.rhd")),
                ),
                (
                    IntanRecordingInterface,
                    "intan",
                    dict(file_path=str(data_path / "intan" / "intan_rhs_test_1.rhs")),
                ),
            ]
        )
        def test_convert_recording_extractor_to_nwb(self, recording_interface, dataset_path, interface_kwargs):
            print(f"\n\n\n TESTING {recording_interface.__name__}...")
            if self.dataset is not None:
                self.dataset.get(dataset_path)
            dataset_stem = Path(dataset_path).stem
            nwbfile_path = self.savedir / f"{recording_interface.__name__}_test_{dataset_stem}.nwb"

            class TestConverter(NWBConverter):
                data_interface_classes = dict(TestRecording=recording_interface)

            converter = TestConverter(source_data=dict(TestRecording=dict(interface_kwargs)))
            converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)
            recording = converter.data_interface_objects["TestRecording"].recording_extractor
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            if np.all(recording.get_channel_offsets() == 0):
                check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=False)
            else:
                new_dtype = recording.get_dtype(return_scaled=False).name[1:]
                traces_1 = recording.get_traces(return_scaled=False).astype(new_dtype)
                unsigned_coercion = (recording.get_channel_offsets() / recording.get_channel_gains()).astype(new_dtype)
                for j, x in enumerate(unsigned_coercion):
                    traces_1[j, :] -= x
                np.testing.assert_almost_equal(traces_1, nwb_recording.get_traces(return_scaled=False))
                nwb_recording.clear_channel_offsets()
            check_recordings_equal(RX1=recording, RX2=nwb_recording, check_times=False, return_scaled=True)


if __name__ == "__main__":
    unittest.main()
