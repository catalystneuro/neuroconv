from unittest import TestCase

import neuroconv
from neuroconv import datainterfaces


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
            "spikeinterface",
            "roiextractors",
            "neo",
            "run_conversion_from_yaml",
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
