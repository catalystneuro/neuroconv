"""
This module is meant to be run stand-alone to emulate a fresh import, not detected automatically via pytest.

Run them by calling: pytest tests/imports.py::TestImportStructure::{test_name}
"""

from unittest import TestCase

from neuroconv import BaseDataInterface


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
            "basedatainterface",
            "basetemporalalignmentinterface",
            "baseextractorinterface",
            "nwbconverter",
            "tools",  # Attached to namespace by NWBConverter import
            "utils",  # Attached to namespace by NWBconverter import
            # Exposed attributes
            "NWBConverter",
            "ConverterPipe",
            "BaseDataInterface",
            "BaseTemporalAlignmentInterface",
            "BaseExtractorInterface",
            "run_conversion_from_yaml",
            "get_format_summaries",
        ]
        assert sorted(current_structure) == sorted(expected_structure)

    def test_tools(self):
        """Python dir() calls (and __dict__ as well) update dynamically based on global imports."""
        from neuroconv import tools

        current_structure = _strip_magic_module_attributes(ls=tools.__dict__)
        expected_structure = [
            # Sub-Packages
            "yaml_conversion_specification",  # Attached to namespace  by top __init__ call of NWBConverter
            # Sub-modules
            "importing",  # Attached to namespace by importing get_package
            "hdmf",
            "nwb_helpers",  # Attached to namespace by top __init__ call of NWBConverter
            "path_expansion",
            "processes",
            # Functions and classes imported on the __init__
            "get_format_summaries",
            "get_package",
            "get_package_version",
            "is_package_installed",
            "deploy_process",
            "data_transfers",
            "LocalPathExpander",
            "get_module",
        ]
        assert sorted(current_structure) == sorted(expected_structure)

    def test_datainterfaces(self):
        from neuroconv import datainterfaces

        current_structure = _strip_magic_module_attributes(ls=datainterfaces.__dict__)

        from neuroconv.datainterfaces import interface_list

        interface_name_list = [interface.__name__ for interface in interface_list]
        expected_structure = [
            # Sub-modules
            "behavior",
            "ecephys",
            "icephys",
            "ophys",
            "text",
            "image",
            # Exposed attributes
            "interface_list",
            "interfaces_by_category",
        ] + interface_name_list

        assert sorted(current_structure) == sorted(expected_structure)


def test_datainterfaces_import():
    """Minimal installation should be able to import interfaces from the .datainterfaces submodule."""
    # Nothing special about SpikeGLX; just need to pick something to import to ensure a minimal install doesn't fail
    from neuroconv.datainterfaces import SpikeGLXRecodingInterface

    assert isinstance(SpikeGLXRecodingInterface, BaseDataInterface)
