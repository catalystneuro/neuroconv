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
            "ecephys",
            "icephys",
            "ophys",
            "behavior",
            # Exposed attributes
            "interface_list",
            # Ecephys
            "RecordingTutorialInterface",
            "SortingTutorialInterface",
            "NeuroscopeRecordingInterface",
            "NeuroscopeLFPInterface",
            "NeuroscopeMultiRecordingTimeInterface",
            "NeuroscopeSortingInterface",
            "SpikeGLXRecordingInterface",
            "SpikeGLXLFPInterface",
            "SpikeGadgetsRecordingInterface",
            "SIPickleRecordingExtractorInterface",
            "SIPickleSortingExtractorInterface",
            "IntanRecordingInterface",
            "CEDRecordingInterface",
            "CellExplorerSortingInterface",
            "BlackrockRecordingExtractorInterface",
            "BlackrockSortingExtractorInterface",
            "OpenEphysRecordingExtractorInterface",
            "OpenEphysSortingExtractorInterface",
            "AxonaRecordingExtractorInterface",
            "AxonaPositionDataInterface",
            "AxonaLFPDataInterface",
            "AxonaUnitRecordingExtractorInterface",
            "NeuralynxRecordingInterface",
            "NeuralynxSortingInterface",
            "PhySortingInterface",
            "KilosortSortingInterface",
            "EDFRecordingInterface",
            # Icephys
            "AbfInterface",
            # Ophys
            "CaimanSegmentationInterface",
            "CnmfeSegmentationInterface",
            "Suite2pSegmentationInterface",
            "ExtractSegmentationInterface",
            "SimaSegmentationInterface",
            "SbxImagingInterface",
            "TiffImagingInterface",
            "Hdf5ImagingInterface",
            "ScanImageImagingInterface",
            # Behavior
            "MovieInterface",
            "DeepLabCutInterface",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)
