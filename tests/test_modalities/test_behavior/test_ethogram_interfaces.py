import re

import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing import MockEthogramInterface
from neuroconv.tools.testing.data_interface_mixins import (
    EthogramInterfaceTestMixin,
    _get_metadata_for_writing,
)


class TestMockEthogramInterface(EthogramInterfaceTestMixin):
    data_interface_cls = MockEthogramInterface
    interface_kwargs = dict(num_samples=300, num_behaviors=4, seed=0)

    def test_bouts_without_ethogram_metadata_key_have_no_catalogue(self, setup_interface):
        metadata = _get_metadata_for_writing(self.interface)
        bouts_entry = metadata["Behavior"]["EthogramBouts"]["mock_ethogram"]
        catalogue_entry = metadata["Behavior"]["Ethograms"]["mock_ethogram"]
        del bouts_entry["ethogram_metadata_key"]

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        behavior_module = nwbfile.processing["behavior"]
        assert behavior_module[bouts_entry["name"]].ethogram is None
        assert catalogue_entry["name"] not in behavior_module.data_interfaces

    def test_source_pose_metadata_key_that_names_no_entry_raises(self, setup_interface):
        metadata = _get_metadata_for_writing(self.interface)
        bouts_entry = metadata["Behavior"]["EthogramBouts"]["mock_ethogram"]
        bouts_entry["source_pose_metadata_key"] = "not_a_pose_estimation"

        expected_message = "metadata_key 'not_a_pose_estimation' was not found in metadata['Pose']['PoseEstimations']."
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            self.interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)
