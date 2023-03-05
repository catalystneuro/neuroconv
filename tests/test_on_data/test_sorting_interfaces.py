from datetime import datetime
from unittest import TestCase

from neuroconv.datainterfaces import (
    BlackrockSortingInterface,
    CellExplorerSortingInterface,
    NeuralynxSortingInterface,
    NeuroScopeSortingInterface,
    PhySortingInterface,
    PlexonSortingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    SortingExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestAxonRecordingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = PhySortingInterface
    interface_kwargs = (dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),)
    save_directory = OUTPUT_PATH


class TestBlackrockSortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BlackrockSortingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev"))
    save_directory = OUTPUT_PATH


class TestCellExplorerSortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CellExplorerSortingInterface
    interface_kwargs = [
        dict(
            file_path=str(
                DATA_PATH / "cellexplorer" / "dataset_1" / "20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
            )
        ),
        dict(file_path=str(DATA_PATH / "cellexplorer" / "dataset_2" / "20170504_396um_0um_merge.spikes.cellinfo.mat")),
        dict(
            file_path=str(DATA_PATH / "cellexplorer" / "dataset_3" / "20170519_864um_900um_merge.spikes.cellinfo.mat")
        ),
    ]
    save_directory = OUTPUT_PATH


class TestNeuralynxSortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuralynxSortingInterface
    interface_kwargs = [
        dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.5.1" / "original_data")),
        dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data")),
    ]
    save_directory = OUTPUT_PATH


class TestNeuroScopeSortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuroScopeSortingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "neuroscope" / "dataset_1"),
        xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2015, 8, 31, 0, 0)


class TestPhySortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = PhySortingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "phy" / "phy_example_0"),
    )
    save_directory = OUTPUT_PATH


class TestPlexonSortingInterface(SortingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = PlexonSortingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "plexon" / "File_plexon_2.plx"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2000, 10, 30, 15, 56, 56)
