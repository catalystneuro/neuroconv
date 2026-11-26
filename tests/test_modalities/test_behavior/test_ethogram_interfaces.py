import re

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing import (
    MockBehavioralSegmentationInterface,
    MockEthogramInterface,
)
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


class TestMockEthogramInterface(EthogramInterfaceTestMixin):
    data_interface_cls = MockEthogramInterface
    interface_kwargs = dict()
    expected_temporal_alignment_keys = ("Walking", "Grooming", "Glancing")

    def test_events_are_an_ethogram_record(self, setup_interface):
        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=_get_metadata_for_writing(self.interface))

        record = nwbfile.events["MockEthogramEvents"]
        assert type(record).__name__ == "EthogramEvents"
        assert record.ethogram is nwbfile.processing["behavior"]["MockEthogram"]
        assert record.labeling_method == "manual"
        assert record.source_software == "MockScorer"
        assert list(record["timestamp"][:]) == [0.5, 1.0, 3.5, 4.0, 5.0, 7.0, 8.0]
        expected_labels = ["Glancing", "Walking", "Grooming", "Glancing", "Walking", "Glancing", "Grooming"]
        assert list(record["label"][:]) == expected_labels

    def test_bouts_are_the_closed_states(self, setup_interface):
        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=_get_metadata_for_writing(self.interface))

        bouts = nwbfile.processing["behavior"]["MockEthogramBouts"]
        assert bouts.source_events is nwbfile.events["MockEthogramEvents"]
        assert list(bouts["start_time"][:]) == [1.0, 3.5, 5.0]
        assert list(bouts["stop_time"][:]) == [3.0, 4.5, 6.5]
        assert list(bouts["label"][:]) == ["Walking", "Grooming", "Walking"]

    def test_event_name_missing_from_the_catalogue_raises(self, setup_interface):
        metadata = _get_metadata_for_writing(self.interface)
        metadata["Events"]["mock_ethogram"]["event_types"]["Walking"]["event_name"] = "Running"

        expected_message = (
            "Event type 'Walking' writes the label 'Running' into 'MockEthogramEvents', but its catalogue "
            "'MockEthogram' has no behavior of that name."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            self.interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
