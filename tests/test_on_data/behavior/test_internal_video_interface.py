import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces import InternalVideoInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


VIDEO_FOLDER_PATH = BEHAVIOR_DATA_PATH / "videos" / "CFR"


class TestInternalVideoInterface(DataInterfaceTestMixin):
    data_interface_cls = InternalVideoInterface
    save_directory = OUTPUT_PATH
    # Stated so the key does not depend on the file stem of each format
    expected_temporal_alignment_keys = ("behavior_camera",)

    @pytest.fixture(
        params=[
            dict(file_path=str(VIDEO_FOLDER_PATH / f"video_{suffix}.{suffix}"), metadata_key="behavior_camera")
            for suffix in ("avi", "flv", "mov", "mp4", "wmv")
        ],
        ids=["avi", "flv", "mov", "mp4", "wmv"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        assert self.interface._default_name in nwbfile.acquisition
        nwbfile.read_io.close()
