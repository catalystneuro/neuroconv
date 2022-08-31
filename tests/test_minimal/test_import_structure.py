from unittest import TestCase

import neuroconv
from neuroconv import datainterfaces
from neuroconv import tools


def _strip_magic_module_attributes(ls: list) -> list:
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
    return list(filter(lambda key: key not in exclude_keys, ls))


class TestImportStructure(TestCase):
    def test_outer_import_structure(self):
        current_structure = _strip_magic_module_attributes(ls=dir(neuroconv))
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
        """Python dir() calls (and __dict__ as well) update dynamically based on global imports."""
        current_structure = _strip_magic_module_attributes(ls=dir(tools))
        minimal_expected_structure = [
            # Sub-modules
            "importing",
            "yaml_conversion_specification",  # imported by outer level __init__
            # Helper functions
            "get_package",
        ]
        for member in minimal_expected_structure:
            self.assertIn(member=member, container=current_structure)

    def test_datainterfaces_import_structure(self):
        current_structure = _strip_magic_module_attributes(ls=dir(datainterfaces))
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
