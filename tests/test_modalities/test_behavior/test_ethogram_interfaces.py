import re

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing import MockBehavioralSegmentationInterface
from neuroconv.tools.testing.data_interface_mixins import (
    EthogramInterfaceTestMixin,
    _get_metadata_for_writing,
)


class TestMockBehavioralSegmentationInterface(EthogramInterfaceTestMixin):
    data_interface_cls = MockBehavioralSegmentationInterface
    interface_kwargs = dict(num_samples=300, num_behaviors=4, seed=0)
    expected_temporal_alignment_keys = ("mock_behavioral_segmentation",)

    def test_bouts_tile_the_frames(self, setup_interface):
        labels = self.interface._get_labels()
        times = self.interface._get_native_times()
        expected_number_of_bouts = np.count_nonzero(np.diff(labels)) + 1
        expected_behaviors = [str(label) for label in np.unique(labels)]

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=_get_metadata_for_writing(self.interface))

        bouts = nwbfile.processing["behavior"]["MockEthogramBouts"]
        catalogue = nwbfile.processing["behavior"]["MockEthogram"]
        assert bouts.bout_concurrency == "partition"
        assert bouts.labeling_method == "automated"
        assert bouts.source_software == "MockSoftware"
        assert len(bouts) == expected_number_of_bouts
        assert bouts["start_time"][0] == times[0]
        np.testing.assert_allclose(bouts["stop_time"][:-1], bouts["start_time"][1:])
        assert list(catalogue["behavior"][:]) == expected_behaviors

    def test_bouts_without_ethogram_metadata_key_have_no_catalogue(self, setup_interface):
        metadata = _get_metadata_for_writing(self.interface)
        bouts_entry = metadata["Behavior"]["EthogramBouts"]["mock_behavioral_segmentation"]
        catalogue_entry = metadata["Behavior"]["Ethograms"]["mock_behavioral_segmentation"]
        del bouts_entry["ethogram_metadata_key"]

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        assert behavior_module[bouts_entry["name"]].ethogram is None
        assert catalogue_entry["name"] not in behavior_module.data_interfaces

    def test_source_pose_metadata_key_that_names_no_entry_raises(self, setup_interface):
        metadata = _get_metadata_for_writing(self.interface)
        bouts_entry = metadata["Behavior"]["EthogramBouts"]["mock_behavioral_segmentation"]
        bouts_entry["source_pose_metadata_key"] = "not_a_pose_estimation"

        expected_message = "metadata_key 'not_a_pose_estimation' was not found in metadata['Pose']['PoseEstimations']."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            self.interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
