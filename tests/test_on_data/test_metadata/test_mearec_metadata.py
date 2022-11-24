import unittest

from neuroconv.datainterfaces import MEArecRecordingInterface

from ..setup_paths import ECEPHY_DATA_PATH


class TestMEArecMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file_path = ECEPHY_DATA_PATH / "mearec" / "mearec_test_10s.h5"
        cls.interface = MEArecRecordingInterface(file_path=file_path)

    def test_nwb_metadata(self):

        nwb_metadata = self.interface.get_metadata()

        assert len(nwb_metadata["Ecephys"]["Device"]) == 1
        assert nwb_metadata["Ecephys"]["Device"][0]["name"] == "Neuronexus-32"
        assert nwb_metadata["Ecephys"]["Device"][0]["description"] == "The ecephys device for the MEArec recording."

        assert len(nwb_metadata["Ecephys"]["ElectrodeGroup"]) == 1
        assert nwb_metadata["Ecephys"]["ElectrodeGroup"][0]["device"] == "Neuronexus-32"

        # TODO: Test ProbeInterface metadata portion here when integrated

        # Recording specific configurations
        assert nwb_metadata["Ecephys"]["ElectricalSeries"]["description"] == (
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


if __name__ == "__main__":
    unittest.main()
