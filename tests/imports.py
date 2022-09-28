# This module is meant for the tests to be run as stand-alone so as to emulate a fresh import
# Run them by using:
# pytest tests/import_structure.py::TestImportStructure::test_name

from unittest import TestCase


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
    def test_top_level(self):
        import neuroconv

        current_structure = _strip_magic_module_attributes(ls=neuroconv.__dict__)
        expected_structure = [
            # Sub-modules
            "nwbconverter",
            "tools",  # Attached to namespace by NWBConverter import
            "utils",  # Attached to namesapce by NWBconverter import
            # Exposed attributes
            "NWBConverter",
            "NWBConverterPipe" "run_conversion_from_yaml",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)

    def test_tools(self):
        """Python dir() calls (and __dict__ as well) update dynamically based on global imports."""

        from neuroconv import tools

        current_structure = _strip_magic_module_attributes(ls=tools.__dict__)
        expected_structure = [
            # Sub-Packages
            "yaml_conversion_specification",  # Attached to namespace  by top __init__ call of NWBConverter
            # Sub-modules
            "importing",  # Attached to namespace by importing get_package
            "nwb_helpers",  # Attached to namespace by top __init__ call of NWBConverter
            # Functions imported on the __init__
            "get_package",
        ]
        self.assertCountEqual(first=current_structure, second=expected_structure)

    def test_datainterfaces(self):
        from neuroconv import datainterfaces

        current_structure = _strip_magic_module_attributes(ls=datainterfaces.__dict__)
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
            "SLEAPInterface",
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
            "TdtRecordingInterface",
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
