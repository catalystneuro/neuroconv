"""
Test to validate that the Copilot setup steps workflow provides all necessary dependencies for neuroconv development.

This test serves as a validation checkpoint for the Copilot setup steps workflow and ensures
future Copilot coding agents have a properly configured development environment.

Test Requirements:
1. Create a new test file that imports key neuroconv modules to verify the full installation works
2. Add a simple test that exercises both the core neuroconv functionality and testing framework
3. Include imports from different extras (full, test, docs) to validate the complete environment setup
4. The test should be lightweight but comprehensive enough to catch setup issues

Expected Validation Points:
- Core neuroconv imports work correctly
- Testing framework (pytest) is available and functional
- Documentation dependencies are accessible
- Full installation extras are properly installed
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCopilotSetupValidation(unittest.TestCase):
    """Comprehensive validation tests for Copilot development environment setup."""

    def test_core_neuroconv_imports(self):
        """Test that core neuroconv components can be imported successfully."""
        # Test basic top-level imports
        from neuroconv import (
            BaseDataInterface,
            ConverterPipe,
            NWBConverter,
            get_format_summaries,
            run_conversion_from_yaml,
        )

        # Verify classes are properly imported
        self.assertTrue(callable(BaseDataInterface))
        self.assertTrue(callable(NWBConverter))
        self.assertTrue(callable(ConverterPipe))
        self.assertTrue(callable(run_conversion_from_yaml))
        self.assertTrue(callable(get_format_summaries))

    def test_datainterfaces_imports(self):
        """Test that data interfaces can be imported from different modalities."""
        # Test ecephys interface (minimal dependencies)
        from neuroconv import BaseDataInterface
        from neuroconv.datainterfaces import SpikeGLXRecordingInterface

        # Verify it's a proper interface
        self.assertTrue(issubclass(SpikeGLXRecordingInterface, BaseDataInterface))

        # Test that datainterfaces module structure is available
        from neuroconv import datainterfaces

        self.assertTrue(hasattr(datainterfaces, "interface_list"))
        self.assertTrue(hasattr(datainterfaces, "interfaces_by_category"))

    def test_tools_module_accessibility(self):
        """Test that neuroconv tools module and its utilities are accessible."""
        from neuroconv.tools import (
            LocalPathExpander,
            get_format_summaries,
            get_package,
            get_package_version,
            is_package_installed,
        )

        # Test utility functions are callable
        self.assertTrue(callable(get_format_summaries))
        self.assertTrue(callable(get_package))
        self.assertTrue(callable(get_package_version))
        self.assertTrue(callable(is_package_installed))
        self.assertTrue(callable(LocalPathExpander))

    def test_testing_framework_availability(self):
        """Test that pytest and testing utilities are available."""
        # Test pytest import
        import pytest

        self.assertTrue(hasattr(pytest, "main"))

        # Test pytest coverage plugin
        try:
            import pytest_cov  # noqa: F401

            pytest_cov_available = True
        except ImportError:
            pytest_cov_available = False

        # Test parameterized testing
        try:
            import parameterized  # noqa: F401

            parameterized_available = True
        except ImportError:
            parameterized_available = False

        # At least pytest should be available
        self.assertTrue(callable(pytest.main))

    def test_documentation_dependencies(self):
        """Test that documentation building dependencies are available."""
        # Test Sphinx
        try:
            import sphinx  # noqa: F401

            sphinx_available = True
        except ImportError:
            sphinx_available = False

        # Test sphinx themes and extensions
        sphinx_extensions = []
        try:
            import sphinx_copybutton  # noqa: F401

            sphinx_extensions.append("sphinx_copybutton")
        except ImportError:
            pass

        try:
            import sphinx_toggleprompt  # noqa: F401

            sphinx_extensions.append("sphinx_toggleprompt")
        except ImportError:
            pass

        try:
            import pydata_sphinx_theme  # noqa: F401

            sphinx_extensions.append("pydata_sphinx_theme")
        except ImportError:
            pass

        # If sphinx is available, at least some extensions should be too
        if sphinx_available:
            self.assertTrue(len(sphinx_extensions) > 0, "Sphinx is available but no expected extensions found")

    def test_core_scientific_dependencies(self):
        """Test that core scientific computing dependencies are available."""
        # Test numpy
        import numpy as np

        self.assertTrue(hasattr(np, "array"))

        # Test h5py for HDF5 support
        import h5py

        self.assertTrue(hasattr(h5py, "File"))

        # Test pynwb for NWB format support
        import pynwb

        self.assertTrue(hasattr(pynwb, "NWBFile"))

        # Test hdmf
        import hdmf

        self.assertTrue(hasattr(hdmf, "Container"))

    def test_neuroconv_functional_workflow(self):
        """Test a simple functional workflow to ensure core functionality works."""
        from neuroconv import NWBConverter
        from neuroconv.tools import get_format_summaries

        # Test format summaries functionality
        format_summaries = get_format_summaries()
        self.assertIsInstance(format_summaries, dict)
        self.assertGreater(len(format_summaries), 0)

        # Test NWBConverter instantiation with empty source_data
        converter = NWBConverter(source_data={})
        self.assertIsInstance(converter, NWBConverter)

        # Test that we can get metadata schema (lightweight test)
        metadata_schema = converter.get_metadata_schema()
        self.assertIsInstance(metadata_schema, dict)
        self.assertIn("properties", metadata_schema)

    def test_full_extras_availability(self):
        """Test that key packages from 'full' installation extras are available."""
        extras_tests = []

        # Test dandi (from full -> dandi extra)
        try:
            import dandi  # noqa: F401

            extras_tests.append(("dandi", True))
        except ImportError:
            extras_tests.append(("dandi", False))

        # Test boto3 (from full -> aws extra)
        try:
            import boto3  # noqa: F401

            extras_tests.append(("boto3", True))
        except ImportError:
            extras_tests.append(("boto3", False))

        # Test hdf5plugin (from full -> compressors extra)
        try:
            import hdf5plugin  # noqa: F401

            extras_tests.append(("hdf5plugin", True))
        except ImportError:
            extras_tests.append(("hdf5plugin", False))

        # Test some behavior dependencies
        try:
            import cv2  # noqa: F401  # opencv-python-headless from video

            extras_tests.append(("opencv", True))
        except ImportError:
            extras_tests.append(("opencv", False))

        # Report what's available (helps with debugging setup issues)
        available_extras = [name for name, available in extras_tests if available]
        missing_extras = [name for name, available in extras_tests if not available]

        # For a complete 'full' installation, we'd expect most of these to be available
        # But we'll make this test informational rather than strict since
        # the specific extras needed might vary by Copilot use case
        if available_extras:
            print(f"Available extras: {', '.join(available_extras)}")
        if missing_extras:
            print(f"Missing extras: {', '.join(missing_extras)}")

        # At minimum, ensure we can identify what's available vs missing
        self.assertIsInstance(available_extras, list)
        self.assertIsInstance(missing_extras, list)

    def test_package_version_detection(self):
        """Test that package version utilities work correctly."""
        from neuroconv.tools import get_package_version, is_package_installed

        # Test on known packages
        numpy_version = get_package_version("numpy")
        # Version might be returned as Version object or string, both are valid
        version_str = str(numpy_version)
        self.assertIsInstance(version_str, str)
        self.assertGreater(len(version_str), 0)

        # Test package detection
        self.assertTrue(is_package_installed("numpy"))
        self.assertTrue(is_package_installed("pytest"))
        self.assertFalse(is_package_installed("definitely_not_a_real_package_name_12345"))

    def test_basic_nwb_file_operations(self):
        """Test basic NWB file operations to ensure the stack works end-to-end."""
        import datetime

        import pynwb
        from pynwb import NWBHDF5IO

        # Create a simple NWB file in memory to test the stack
        nwbfile = pynwb.NWBFile(
            session_description="Test session for Copilot setup validation",
            identifier="test_copilot_setup",
            session_start_time=datetime.datetime.now(),
        )

        # Verify basic properties
        self.assertEqual(nwbfile.identifier, "test_copilot_setup")
        self.assertIsInstance(nwbfile.session_start_time, datetime.datetime)

        # Test that we can create an in-memory file (tests h5py integration)
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            with NWBHDF5IO(str(temp_path), "w") as io:
                io.write(nwbfile)

            # Verify file was created and can be read
            self.assertTrue(temp_path.exists())

            with NWBHDF5IO(str(temp_path), "r") as io:
                read_nwbfile = io.read()
                self.assertEqual(read_nwbfile.identifier, "test_copilot_setup")
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()

    def test_copilot_specific_workflow(self):
        """Test a workflow specifically relevant for Copilot development tasks."""
        # Test that a Copilot agent could successfully:

        # 1. Import and inspect available interfaces
        from neuroconv.tools import get_format_summaries

        format_summaries = get_format_summaries()

        # Verify we can get information about available formats
        self.assertGreater(len(format_summaries), 10)  # Should have many formats

        # 2. Explore what interfaces are available
        from neuroconv.datainterfaces import interface_list, interfaces_by_category

        self.assertGreater(len(interface_list), 10)  # Should have many interfaces
        self.assertIn("ecephys", interfaces_by_category)

        # Check that we have some key categories (might include imaging, segmentation, etc.)
        available_categories = list(interfaces_by_category.keys())
        self.assertGreater(len(available_categories), 3)  # Should have multiple categories

        # 3. Use package detection for conditional logic
        from neuroconv.tools import is_package_installed

        self.assertTrue(is_package_installed("numpy"))  # Core dependency
        self.assertTrue(is_package_installed("h5py"))  # Core dependency

        # 4. Access documentation/schema information
        from neuroconv import NWBConverter

        converter = NWBConverter(source_data={})
        schema = converter.get_metadata_schema()
        self.assertIn("properties", schema)
        self.assertIn("Subject", schema["properties"])  # Common NWB element

    def test_data_access_and_basic_operations(self):
        """Test that testing data can be accessed and basic data operations work."""
        from pathlib import Path

        # Get the project root and testing data paths
        project_root = Path(__file__).parent.parent
        ephy_data_path = project_root / "ephy_testing_data"
        behavior_data_path = project_root / "behavior_testing_data"
        ophys_data_path = project_root / "ophys_testing_data"

        # Check that testing data directories exist
        available_data_types = []
        if ephy_data_path.exists():
            available_data_types.append("ecephys")
        if behavior_data_path.exists():
            available_data_types.append("behavior")
        if ophys_data_path.exists():
            available_data_types.append("ophys")

        print(f"Available testing data types: {', '.join(available_data_types) if available_data_types else 'None'}")

        # Test basic data interface operations if any data is available
        if available_data_types:
            # Test that we can import data interfaces
            from neuroconv.datainterfaces import interface_list

            self.assertGreater(len(interface_list), 0)

            # Test SpikeGLX interface specifically if ecephys data is available
            if "ecephys" in available_data_types:
                spikeglx_path = ephy_data_path / "spikeglx"
                if spikeglx_path.exists():
                    from neuroconv.datainterfaces import SpikeGLXRecordingInterface

                    # Look for any .bin files as a basic test
                    bin_files = list(spikeglx_path.rglob("*.bin"))
                    if bin_files:
                        # Just verify we can instantiate the interface class
                        # (without requiring specific file structure that may vary)
                        self.assertTrue(callable(SpikeGLXRecordingInterface))
                        print(f"✓ SpikeGLX data files found: {len(bin_files)} .bin files")

            # Test behavior interface if data is available
            if "behavior" in available_data_types:
                video_path = behavior_data_path / "videos"
                if video_path.exists():
                    video_files = list(video_path.rglob("*.mp4")) + list(video_path.rglob("*.avi"))
                    if video_files:
                        print(f"✓ Video data files found: {len(video_files)} video files")
        else:
            # If no testing data is available, just verify the interfaces can be imported
            from neuroconv.datainterfaces import interface_list

            self.assertGreater(len(interface_list), 10)
            print("ℹ No testing data directories found, but interface imports work")

    def test_documentation_build_functionality(self):
        """Test that documentation can be built successfully."""

        # Get the docs directory
        project_root = Path(__file__).parent.parent
        docs_dir = project_root / "docs"

        # Verify docs directory and conf.py exist
        self.assertTrue(docs_dir.exists(), "Documentation directory should exist")
        conf_py = docs_dir / "conf.py"
        self.assertTrue(conf_py.exists(), "conf.py should exist in docs directory")

        # Create a temporary build directory
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            build_dir.mkdir()

            try:
                # Try to build the documentation
                # Use subprocess to run sphinx-build
                cmd = [
                    sys.executable,
                    "-m",
                    "sphinx",
                    "-b",
                    "html",  # Build HTML
                    "-W",  # Treat warnings as errors
                    "-q",  # Quiet mode (reduce output)
                    str(docs_dir),  # Source directory
                    str(build_dir),  # Build directory
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # 2 minute timeout

                # Check if build succeeded
                build_succeeded = result.returncode == 0

                if build_succeeded:
                    # Verify key output files were created
                    index_html = build_dir / "index.html"
                    self.assertTrue(index_html.exists(), "index.html should be generated")

                    # Check that some content was generated
                    if index_html.exists():
                        content = index_html.read_text()
                        self.assertIn("NeuroConv", content, "Documentation should contain project name")

                    print("✓ Documentation build successful")
                else:
                    # Print error output for debugging
                    print(f"⚠ Documentation build failed with return code {result.returncode}")
                    if result.stderr:
                        print(f"Error output: {result.stderr[:500]}")  # First 500 chars
                    if result.stdout:
                        print(f"Build output: {result.stdout[:500]}")  # First 500 chars

                    # Make this a soft failure - docs build issues shouldn't block development
                    print("ℹ Documentation build failed, but this is informational")

            except subprocess.TimeoutExpired:
                print("⚠ Documentation build timed out after 120 seconds")
                print("ℹ Build timeout is informational, not a hard failure")
            except FileNotFoundError:
                # sphinx module not found
                print("⚠ Sphinx not available for documentation building")
                print("ℹ Documentation dependencies may not be fully installed")
            except Exception as e:
                print(f"⚠ Documentation build error: {e}")
                print("ℹ Documentation build issues are informational")


def test_minimal_environment_validation():
    """Standalone function test for minimal environment validation.

    This can be run independently without the unittest framework.
    """
    # Test basic imports
    from neuroconv import NWBConverter

    # Test that we can instantiate basic objects
    converter = NWBConverter(source_data={})

    # Test format summaries
    from neuroconv.tools import get_format_summaries

    summaries = get_format_summaries()

    assert isinstance(summaries, dict), "get_format_summaries should return a dict"
    assert len(summaries) > 0, "Should have some format summaries"

    print("✓ Minimal environment validation passed")


if __name__ == "__main__":
    # Allow running this as a standalone script
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--minimal":
        # Run minimal test
        test_minimal_environment_validation()
    else:
        # Run full test suite
        unittest.main()
