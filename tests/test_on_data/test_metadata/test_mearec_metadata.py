import unittest
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree
from dateutil import tz
from datetime import datetime

from pynwb import NWBHDF5IO
from neuroconv.datainterfaces import MEArecRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


class TestMEArecMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file_path = ECEPHY_DATA_PATH / "mearec" / "mearec_test_10s.h5"
        cls.interface = MEArecRecordingInterface(file_path=file_path)

        cls.tmpdir = Path(mkdtemp())
        cls.nwbfile_path = cls.tmpdir / "mearec_meadata_test.nwb"
        metadata = cls.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")))
        cls.interface.run_conversion(nwbfile_path=cls.nwbfile_path, metadata=metadata)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def test_neuroconv_metadata(self):
        neuroconv_metadata = self.interface.get_metadata()

        assert len(neuroconv_metadata["Ecephys"]["Device"]) == 1
        assert neuroconv_metadata["Ecephys"]["Device"][0]["name"] == "Neuronexus-32"
        assert (
            neuroconv_metadata["Ecephys"]["Device"][0]["description"] == "The ecephys device for the MEArec recording."
        )

        assert len(neuroconv_metadata["Ecephys"]["ElectrodeGroup"]) == 1
        assert neuroconv_metadata["Ecephys"]["ElectrodeGroup"][0]["device"] == "Neuronexus-32"

        # TODO: Test ProbeInterface metadata portion here when integrated

        # Recording specific configurations
        assert neuroconv_metadata["Ecephys"]["ElectricalSeries"]["description"] == (
            '{"angle_tol": 15, "bursting": false, "chunk_duration": 0, "color_noise_floor": 1, '
            '"color_peak": 300, "color_q": 2, "drift_mode": "slow", "drifting": false, '
            '"duration": 10.0, "exp_decay": 0.2, "extract_waveforms": false, '
            '"far_neurons_exc_inh_ratio": 0.8, "far_neurons_max_amp": 10, "far_neurons_n": 300, '
            '"far_neurons_noise_floor": 0.5, "fast_drift_max_jump": 20, "fast_drift_min_jump": 5, '
            '"fast_drift_period": 10, "filter": true, "filter_cutoff": [300, 6000], "filter_order": 3, '
            '"max_burst_duration": 100, "modulation": "electrode", "mrand": 1, '
            '"n_burst_spikes": 10, "n_bursting": null, "n_drifting": null, "n_neurons": 10, '
            '"noise_color": false, "noise_half_distance": 30, "noise_level": 10, '
            '"noise_mode": "uncorrelated", "overlap": false, "preferred_dir": [0, 0, 1], '
            '"sdrand": 0.05, "shape_mod": false, "shape_stretch": 30.0, "slow_drift_velocity": 5, '
            '"sync_jitt": 1, "sync_rate": null, "t_start_drift": 0}'
        )

    def test_nwb_electrical_series_channel_conversions(self):
        """MEArec writes directly to float32 microVolts, so channel_conversion should be None."""
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            assert nwbfile.acquisition["ElectricalSeries"].channel_conversion is None

    def test_nwb_electrode_cols(self):
        """MEArec writes directly to float32 microVolts, so channel_conversion should be None."""
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()

            for optional_column in ["x", "y", "z", "imp", "filtering"]:
                assert not hasattr(
                    nwbfile.electrodes, optional_column
                ), f"Example data for MEArec does not have data for optional column '{field}', but column was added to NWB file!"


if __name__ == "__main__":
    unittest.main()
