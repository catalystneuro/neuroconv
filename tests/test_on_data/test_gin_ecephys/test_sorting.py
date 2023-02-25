import unittest
import pytest
from datetime import datetime

import numpy as np
from parameterized import parameterized, param
from spikeinterface.core.testing import check_sortings_equal as check_sorting_equal_si
from spikeinterface.extractors import NwbSortingExtractor as NwbSortingExtractorSI

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    CellExplorerSortingInterface,
    NeuralynxSortingInterface,
    NeuroScopeSortingInterface,
    PhySortingInterface,
    KiloSortSortingInterface,
    BlackrockSortingInterface,
    PlexonSortingInterface,
)

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH

if not DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    interface_name = param.kwargs["data_interface"].__name__
    reduced_interface_name = interface_name.replace("Recording", "").replace("Interface", "").replace("Sorting", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestEcephysSortingNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_sorting_list = [
        param(
            data_interface=KiloSortSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),
        ),
        param(
            data_interface=BlackrockSortingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev")),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_1" / "20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
                )
            ),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "cellexplorer" / "dataset_2" / "20170504_396um_0um_merge.spikes.cellinfo.mat")
            ),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_3" / "20170519_864um_900um_merge.spikes.cellinfo.mat"
                )
            ),
        ),
        param(
            data_interface=NeuralynxSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.5.1" / "original_data")),
            case_name="mono_electrodes",
        ),
        param(
            data_interface=NeuralynxSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data")),
            case_name="tetrodes",
        ),
        param(
            data_interface=PlexonSortingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "plexon" / "File_plexon_2.plx")),
            case_name="plexon_sorting",
        ),
    ]

    for spikeextractors_backend in [False, True]:
        parameterized_sorting_list.append(
            param(
                data_interface=NeuroScopeSortingInterface,
                interface_kwargs=dict(
                    folder_path=str(DATA_PATH / "neuroscope" / "dataset_1"),
                    xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend_{spikeextractors_backend}",
            )
        )

        parameterized_sorting_list.append(
            param(
                data_interface=PhySortingInterface,
                interface_kwargs=dict(
                    folder_path=str(DATA_PATH / "phy" / "phy_example_0"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend_{spikeextractors_backend}",
            )
        )

    @parameterized.expand(input=parameterized_sorting_list, name_func=custom_name_func)
    def test_convert_sorting_extractor_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestSorting=data_interface)

        converter = TestConverter(source_data=dict(TestSorting=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestSorting"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        sorting = converter.data_interface_objects["TestSorting"].sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sf = 30000
            sorting.set_sampling_frequency(sf)

        # NWBSortingExtractor on spikeinterface does not yet support loading data written from multiple segment.
        if sorting.get_num_segments() == 1:
            nwb_sorting = NwbSortingExtractorSI(file_path=nwbfile_path, sampling_frequency=sf)
            # In the NWBSortingExtractor, since unit_names could be not unique,
            # table "ids" are loaded as unit_ids. Here we rename the original sorting accordingly
            sorting_renamed = sorting.select_units(
                unit_ids=sorting.unit_ids, renamed_unit_ids=np.arange(len(sorting.unit_ids))
            )
            check_sorting_equal_si(SX1=sorting_renamed, SX2=nwb_sorting)


if __name__ == "__main__":
    unittest.main()
