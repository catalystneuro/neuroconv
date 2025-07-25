import unittest
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
import pytest
from pynwb import NWBFile

from neuroconv import (
    BaseDataInterface,
    BaseTemporalAlignmentInterface,
    ConverterPipe,
    NWBConverter,
)

try:
    from ndx_events import LabeledEvents

    HAVE_NDX_EVENTS = True
except ImportError:
    HAVE_NDX_EVENTS = False


def test_converter():
    if HAVE_NDX_EVENTS:
        test_dir = Path(mkdtemp())
        nwbfile_path = str(test_dir / "extension_test.nwb")

        class NdxEventsInterface(BaseTemporalAlignmentInterface):
            def __init__(self, verbose: bool = False):
                self._timestamps = np.array([0.0, 0.5, 0.6, 2.0, 2.05, 3.0, 3.5, 3.6, 4.0])
                self._original_timestamps = np.array(self._timestamps)

            def get_original_timestamps(self) -> np.ndarray:
                return self._original_timestamps

            def get_timestamps(self) -> np.ndarray:
                return self._timestamps

            def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
                self._timestamps = aligned_timestamps

            def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict):
                events = LabeledEvents(
                    name="LabeledEvents",
                    description="events from my experiment",
                    timestamps=self.get_timestamps(),
                    resolution=1e-5,
                    data=[0, 1, 2, 3, 5, 0, 1, 2, 4],
                    labels=["trial_start", "cue_onset", "cue_offset", "response_left", "response_right", "reward"],
                )
                nwbfile.add_acquisition(events)

        class ExtensionTestNWBConverter(NWBConverter):
            data_interface_classes = dict(NdxEvents=NdxEventsInterface)

        converter = ExtensionTestNWBConverter(source_data=dict(NdxEvents=dict()))
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        rmtree(test_dir)


class TestNWBConverterAndPipeInitialization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class InterfaceA(BaseTemporalAlignmentInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def get_original_timestamps(self):
                pass

            def get_timestamps(self):
                pass

            def set_aligned_timestamps(self):
                pass

            def add_to_nwbfile(self):
                pass

        cls.InterfaceA = InterfaceA

        class InterfaceB(BaseDataInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def add_to_nwbfile(self):
                pass

        cls.InterfaceB = InterfaceB

    def test_child_class_source_data_init(self):
        class NWBConverterChild(NWBConverter):
            data_interface_classes = dict(InterfaceA=self.InterfaceA, InterfaceB=self.InterfaceB)

        source_data = dict(InterfaceA=dict(), InterfaceB=dict())
        converter = NWBConverterChild(source_data)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

    def test_pipe_list_init(self):
        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_list = [interface_a, interface_b]
        converter = ConverterPipe(data_interfaces=data_interfaces_list)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

        assert converter.data_interface_objects["InterfaceA"] is interface_a
        assert converter.data_interface_objects["InterfaceB"] is interface_b

    def test_pipe_list_dict(self):
        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_dict = dict(InterfaceA=interface_a, InterfaceB=interface_b)
        converter = ConverterPipe(data_interfaces=data_interfaces_dict)

        data_interface_names = converter.data_interface_classes.keys()
        assert ["InterfaceA", "InterfaceB"] == list(data_interface_names)

        assert converter.data_interface_classes["InterfaceA"] is self.InterfaceA
        assert converter.data_interface_classes["InterfaceB"] is self.InterfaceB

        assert converter.data_interface_objects["InterfaceA"] is interface_a
        assert converter.data_interface_objects["InterfaceB"] is interface_b

    def test_consistent_init_pipe_vs_nwb(self):
        class NWBConverterChild(NWBConverter):
            data_interface_classes = dict(InterfaceA=self.InterfaceA, InterfaceB=self.InterfaceB)

        source_data = dict(InterfaceA=dict(), InterfaceB=dict())
        converter_child_class = NWBConverterChild(source_data)

        interface_a = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_dict = dict(InterfaceA=interface_a, InterfaceB=interface_b)
        converter_arguments = ConverterPipe(data_interfaces=data_interfaces_dict)

        assert converter_arguments.data_interface_classes == converter_child_class.data_interface_classes

    def test_unique_names_with_list_argument(self):
        interface_a = self.InterfaceA()
        interface_a2 = self.InterfaceA()
        interface_b = self.InterfaceB()
        data_interfaces_list = [interface_a, interface_b, interface_a2]
        converter = ConverterPipe(data_interfaces=data_interfaces_list)

        data_interface_names = list(converter.data_interface_objects.keys())
        expected_interface_names = ["InterfaceA001", "InterfaceB", "InterfaceA002"]
        self.assertListEqual(data_interface_names, expected_interface_names)


class TestNWBConverterGetMetadataWithFiles(unittest.TestCase):
    """Test the new get_metadata functionality that accepts YAML/JSON file paths."""

    @classmethod
    def setUpClass(cls):
        """Set up test converter and file paths."""

        class TestInterface(BaseDataInterface):
            def __init__(self, **source_data):
                super().__init__(**source_data)

            def get_metadata(self):
                metadata = super().get_metadata()
                metadata["NWBFile"]["session_description"] = "Auto-generated session description"
                metadata["NWBFile"]["lab"] = "Auto-generated lab"
                metadata["TestInterface"] = {"auto_field": "auto_value"}
                return metadata

            def add_to_nwbfile(self):
                pass

        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(TestInterface=TestInterface)

        cls.TestInterface = TestInterface
        cls.TestNWBConverter = TestNWBConverter

        # Get paths to test metadata files
        test_dir = Path(__file__).parent
        cls.yaml_file_path = test_dir / "test_metadata.yaml"
        cls.json_file_path = test_dir / "test_metadata.json"

    def setUp(self):
        """Create a fresh converter instance for each test."""
        source_data = dict(TestInterface=dict())
        self.converter = self.TestNWBConverter(source_data)

    def test_get_metadata_without_file_backward_compatibility(self):
        """Test that get_metadata() still works without parameters (backward compatibility)."""
        metadata = self.converter.get_metadata()

        # Should contain auto-generated metadata
        assert "NWBFile" in metadata
        assert metadata["NWBFile"]["session_description"] == "Auto-generated session description"
        assert metadata["NWBFile"]["lab"] == "Auto-generated lab"
        assert "TestInterface" in metadata
        assert metadata["TestInterface"]["auto_field"] == "auto_value"

    def test_get_metadata_with_yaml_file(self):
        """Test loading metadata from a YAML file."""
        metadata = self.converter.get_metadata(metadata_file_path=self.yaml_file_path)

        # Should contain merged metadata from YAML file
        assert "NWBFile" in metadata
        assert metadata["NWBFile"]["session_description"] == "Test session from YAML file"
        assert metadata["NWBFile"]["lab"] == "Test Lab from YAML"
        assert metadata["NWBFile"]["institution"] == "Test Institution from YAML"
        assert metadata["NWBFile"]["experimenter"] == ["John Doe", "Jane Smith"]
        assert metadata["NWBFile"]["related_publications"] == ["doi:10.1000/test"]

        # Should contain YAML-specific fields
        assert "Custom" in metadata
        assert metadata["Custom"]["yaml_specific_field"] == "This field only exists in YAML"
        assert metadata["Custom"]["nested_field"]["sub_field"] == "nested value from YAML"

        # Should still contain auto-generated fields that weren't overridden
        assert "TestInterface" in metadata
        assert metadata["TestInterface"]["auto_field"] == "auto_value"

    def test_get_metadata_with_json_file(self):
        """Test loading metadata from a JSON file."""
        metadata = self.converter.get_metadata(metadata_file_path=self.json_file_path)

        # Should contain merged metadata from JSON file
        assert "NWBFile" in metadata
        assert metadata["NWBFile"]["session_description"] == "Test session from JSON file"
        assert metadata["NWBFile"]["lab"] == "Test Lab from JSON"
        assert metadata["NWBFile"]["institution"] == "Test Institution from JSON"
        assert metadata["NWBFile"]["experimenter"] == ["Alice Johnson"]
        assert metadata["NWBFile"]["keywords"] == ["json", "test", "metadata"]

        # Should contain JSON-specific fields
        assert "Custom" in metadata
        assert metadata["Custom"]["json_specific_field"] == "This field only exists in JSON"
        assert metadata["Custom"]["nested_field"]["sub_field"] == "nested value from JSON"

        # Should still contain auto-generated fields that weren't overridden
        assert "TestInterface" in metadata
        assert metadata["TestInterface"]["auto_field"] == "auto_value"

    def test_get_metadata_file_overrides_auto_generated(self):
        """Test that file metadata properly overrides auto-generated metadata."""
        # Get auto-generated metadata
        auto_metadata = self.converter.get_metadata()

        # Get metadata with YAML file
        yaml_metadata = self.converter.get_metadata(metadata_file_path=self.yaml_file_path)

        # File values should override auto-generated values
        assert auto_metadata["NWBFile"]["session_description"] == "Auto-generated session description"
        assert yaml_metadata["NWBFile"]["session_description"] == "Test session from YAML file"

        assert auto_metadata["NWBFile"]["lab"] == "Auto-generated lab"
        assert yaml_metadata["NWBFile"]["lab"] == "Test Lab from YAML"

    def test_get_metadata_with_invalid_file_path(self):
        """Test error handling for invalid file paths."""
        with pytest.raises(AssertionError):
            self.converter.get_metadata(metadata_file_path="/nonexistent/path/metadata.yaml")

    def test_get_metadata_with_none_file_path(self):
        """Test that passing None as file path works (same as no parameter)."""
        metadata_no_param = self.converter.get_metadata()
        metadata_none_param = self.converter.get_metadata(metadata_file_path=None)

        # Should be functionally identical (excluding random identifiers)
        assert (
            metadata_no_param["NWBFile"]["session_description"] == metadata_none_param["NWBFile"]["session_description"]
        )
        assert metadata_no_param["NWBFile"]["lab"] == metadata_none_param["NWBFile"]["lab"]
        assert metadata_no_param["TestInterface"] == metadata_none_param["TestInterface"]

    def test_get_metadata_deep_merge_behavior(self):
        """Test that deep merge properly combines nested structures."""
        metadata = self.converter.get_metadata(metadata_file_path=self.yaml_file_path)

        # Should have both auto-generated and YAML fields in nested structures
        assert "Behavior" in metadata
        assert "Videos" in metadata["Behavior"]

        # YAML file adds video metadata
        yaml_video_found = False
        for video in metadata["Behavior"]["Videos"]:
            if video.get("name") == "test_video_yaml":
                yaml_video_found = True
                assert video["description"] == "Test video from YAML metadata"
        assert yaml_video_found, "YAML video metadata should be present"


def test_get_metadata_yaml_json_integration():
    """Integration test comparing YAML and JSON loading behavior."""

    class SimpleInterface(BaseDataInterface):
        def add_to_nwbfile(self):
            pass

    class SimpleConverter(NWBConverter):
        data_interface_classes = dict(SimpleInterface=SimpleInterface)

    converter = SimpleConverter(source_data=dict(SimpleInterface=dict()))

    test_dir = Path(__file__).parent
    yaml_path = test_dir / "test_metadata.yaml"
    json_path = test_dir / "test_metadata.json"

    yaml_metadata = converter.get_metadata(metadata_file_path=yaml_path)
    json_metadata = converter.get_metadata(metadata_file_path=json_path)

    # Both should have loaded their respective custom fields
    assert "yaml_specific_field" in yaml_metadata["Custom"]
    assert "json_specific_field" in json_metadata["Custom"]

    # Values should be different as expected
    assert yaml_metadata["NWBFile"]["session_description"] != json_metadata["NWBFile"]["session_description"]
    assert yaml_metadata["Custom"]["nested_field"]["sub_field"] != json_metadata["Custom"]["nested_field"]["sub_field"]


def test_conversion_with_yaml_json_metadata_integration():
    """Integration test that runs actual NWB conversion using YAML/JSON metadata."""
    from datetime import datetime
    from shutil import rmtree
    from tempfile import mkdtemp

    from pynwb import NWBHDF5IO

    class IntegrationTestInterface(BaseDataInterface):
        def get_metadata(self, metadata_file_path=None):
            metadata = super().get_metadata(metadata_file_path=metadata_file_path)
            metadata["NWBFile"]["session_description"] = "Integration test session"
            return metadata

        def add_to_nwbfile(self, nwbfile, metadata, **conversion_options):
            # Add some dummy data to test the conversion
            import numpy as np
            from pynwb.misc import AnnotationSeries

            annotations = AnnotationSeries(
                name="test_annotations",
                description="Test annotations for integration test",
                data=["start", "middle", "end"],
                timestamps=np.array([0.0, 1.0, 2.0]),
            )
            nwbfile.add_acquisition(annotations)

    class IntegrationTestConverter(NWBConverter):
        data_interface_classes = dict(TestInterface=IntegrationTestInterface)

    # Test with YAML metadata
    test_dir = Path(mkdtemp())
    converter = IntegrationTestConverter(source_data=dict(TestInterface=dict()))

    yaml_path = Path(__file__).parent / "test_metadata.yaml"
    nwbfile_path_yaml = test_dir / "test_yaml_integration.nwb"

    # Get metadata with YAML file and add required session_start_time
    metadata = converter.get_metadata(metadata_file_path=yaml_path)
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

    # Run conversion
    converter.run_conversion(nwbfile_path=nwbfile_path_yaml, metadata=metadata, overwrite=True)

    # Verify the file was created and contains YAML metadata
    assert nwbfile_path_yaml.exists()
    with NWBHDF5IO(nwbfile_path_yaml, mode="r") as io:
        nwbfile = io.read()

        # Check that YAML metadata was incorporated
        assert nwbfile.session_description == "Test session from YAML file"
        assert nwbfile.lab == "Test Lab from YAML"
        assert nwbfile.institution == "Test Institution from YAML"
        assert list(nwbfile.experimenter) == ["John Doe", "Jane Smith"]

        # Check that the interface data was added
        assert "test_annotations" in nwbfile.acquisition
        annotations = nwbfile.acquisition["test_annotations"]
        assert annotations.description == "Test annotations for integration test"

    # Test with JSON metadata
    json_path = Path(__file__).parent / "test_metadata.json"
    nwbfile_path_json = test_dir / "test_json_integration.nwb"

    # Get metadata with JSON file and add required session_start_time
    metadata = converter.get_metadata(metadata_file_path=json_path)
    metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

    # Run conversion
    converter.run_conversion(nwbfile_path=nwbfile_path_json, metadata=metadata, overwrite=True)

    # Verify the file was created and contains JSON metadata
    assert nwbfile_path_json.exists()
    with NWBHDF5IO(nwbfile_path_json, mode="r") as io:
        nwbfile = io.read()

        # Check that JSON metadata was incorporated
        assert nwbfile.session_description == "Test session from JSON file"
        assert nwbfile.lab == "Test Lab from JSON"
        assert nwbfile.institution == "Test Institution from JSON"
        assert list(nwbfile.experimenter) == ["Alice Johnson"]

        # Check that the interface data was added
        assert "test_annotations" in nwbfile.acquisition
        annotations = nwbfile.acquisition["test_annotations"]
        assert annotations.description == "Test annotations for integration test"

    # Clean up
    rmtree(test_dir)


def test_base_data_interface_yaml_json_metadata():
    """Test that BaseDataInterface also supports YAML/JSON metadata loading."""

    class TestInterface(BaseDataInterface):
        def add_to_nwbfile(self, nwbfile, metadata, **conversion_options):
            pass

    interface = TestInterface()
    test_dir = Path(__file__).parent

    # Test YAML loading
    yaml_path = test_dir / "test_metadata.yaml"
    yaml_metadata = interface.get_metadata(metadata_file_path=yaml_path)

    assert yaml_metadata["NWBFile"]["session_description"] == "Test session from YAML file"
    assert yaml_metadata["NWBFile"]["lab"] == "Test Lab from YAML"
    assert "yaml_specific_field" in yaml_metadata["Custom"]

    # Test JSON loading
    json_path = test_dir / "test_metadata.json"
    json_metadata = interface.get_metadata(metadata_file_path=json_path)

    assert json_metadata["NWBFile"]["session_description"] == "Test session from JSON file"
    assert json_metadata["NWBFile"]["lab"] == "Test Lab from JSON"
    assert "json_specific_field" in json_metadata["Custom"]

    # Test backward compatibility
    default_metadata = interface.get_metadata()
    assert default_metadata["NWBFile"]["session_description"] == ""
    assert "Custom" not in default_metadata
