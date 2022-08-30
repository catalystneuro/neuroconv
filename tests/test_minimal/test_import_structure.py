from unittest import TestCase

import neuroconv
from neuroconv import datainterfaces
from neuroconv import tools


def _strip_magic_module_attributes(dictionary: dict) -> dict:
    exclude_keys = [
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__path__",
        "__file__",
        "__cached__",
        "__builtins__",
    ]
    return {k: v for k, v in dictionary.items() if k not in exclude_keys}


class TestImportStructure(TestCase):
    def test_outer_import_structure(self):
        current_structure = _strip_magic_module_attributes(dictionary=neuroconv.__dict__)
        expected_structure = [
            # Sub-modules
            "nwbconverter",
            "basedatainterface",
            "baseextractorinterface",
            "datainterfaces",
            "tools",
            "utils",
            # Exposed attributes
            "NWBConverter",
            "run_conversion_from_yaml",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)

    def test_tools_import_structure(self):
        current_structure = _strip_magic_module_attributes(dictionary=tools.__dict__)
        expected_structure = [
            # Sub-modules
            "importing",
            "nwb_helpers",
            "yaml_conversion_specification",
            "hdmf",
            "data_transfers",
            # Helper functions
            "get_package",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)

    def test_datainterfaces_import_structure(self):
        current_structure = _strip_magic_module_attributes(dictionary=datainterfaces.__dict__)
        expected_structure = [
            # Sub-modules
            "behavior",
            "ecephys",
            "icephys",
            "ophys",
            # Exposed attributes
            "interface_list",
            # Behavior
            "DeepLabCutInterface",
            "MovieInterface",
            # Ecephys
            "AxonaRecordingInterface",
            "AxonaPositionDataInterface",
            "AxonaLFPDataInterface",
            "AxonaUnitRecordingInterface",
            "BlackrockRecordingInterface",
            "BlackrockSortingInterface",
            "CEDRecordingInterface",
            "CellExplorerSortingInterface",
            "EDFRecordingInterface",
            "IntanRecordingInterface",
            "KiloSortSortingInterface",
            "NeuralynxRecordingInterface",
            "NeuralynxSortingInterface",
            "NeuroScopeRecordingInterface",
            "NeuroScopeLFPInterface",
            "NeuroScopeMultiRecordingTimeInterface",
            "NeuroScopeSortingInterface",
            "OpenEphysRecordingInterface",
            "OpenEphysSortingInterface",
            "PhySortingInterface",
            "SpikeGLXRecordingInterface",
            "SpikeGLXLFPInterface",
            "SpikeGadgetsRecordingInterface",
            "SIPickleRecordingInterface",
            "SIPickleSortingInterface",
            # Icephys
            "AbfInterface",
            # Ophys
            "CaimanSegmentationInterface",
            "CnmfeSegmentationInterface",
            "ExtractSegmentationInterface",
            "Hdf5ImagingInterface",
            "SbxImagingInterface",
            "ScanImageImagingInterface",
            "SimaSegmentationInterface",
            "Suite2pSegmentationInterface",
            "TiffImagingInterface",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)
