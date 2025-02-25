"""Tests for the warning when nwbfile_path does not end with .nwb."""

import os
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import Optional

import pytest
from pynwb import NWBFile

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.nwbconverter import NWBConverter


class MinimalDataInterface(BaseDataInterface):
    """A minimal data interface for testing."""

    def __init__(self, verbose=False):
        super().__init__(verbose=verbose)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: Optional[dict], **conversion_options) -> None:
        """Add data to an NWBFile."""
        pass


class TestNWBFileExtensionWarning(unittest.TestCase):
    """Test that a warning is raised when nwbfile_path does not end with .nwb."""

    def setUp(self):
        """Set up the test by creating a minimal converter and data interface."""
        # Create a minimal converter with no data interfaces
        class MinimalConverter(NWBConverter):
            """A minimal converter with no data interfaces."""

            data_interface_classes = {}

        self.converter = MinimalConverter(source_data={})
        self.data_interface = MinimalDataInterface()

    def test_warning_raised_for_non_nwb_extension(self):
        """Test that a warning is raised when nwbfile_path does not end with .nwb."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file path without .nwb extension
            non_nwb_path = Path(temp_dir) / "test_file.txt"
            
            # Check that a warning is raised
            with pytest.warns(UserWarning, match="does not end with '.nwb'"):
                # We don't actually need to run the full conversion, just call the method
                # that checks the file extension
                self.converter.run_conversion(
                    nwbfile_path=non_nwb_path,
                    metadata={
                        "NWBFile": {
                            "session_description": "test", 
                            "identifier": "test",
                            "session_start_time": "2023-01-01T12:00:00"
                        }
                    },
                    overwrite=True,
                )

    def test_no_warning_for_nwb_extension(self):
        """Test that no warning is raised when nwbfile_path ends with .nwb."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file path with .nwb extension
            nwb_path = Path(temp_dir) / "test_file.nwb"
            
            # Check that no warning is raised
            with warnings.catch_warnings(record=True) as w:
                # Filter out other warnings that might be raised
                warnings.filterwarnings("always", category=UserWarning)
                
                # We don't actually need to run the full conversion, just call the method
                # that checks the file extension
                self.converter.run_conversion(
                    nwbfile_path=nwb_path,
                    metadata={
                        "NWBFile": {
                            "session_description": "test", 
                            "identifier": "test",
                            "session_start_time": "2023-01-01T12:00:00"
                        }
                    },
                    overwrite=True,
                )
                
                # Check that no warning about file extension was raised
                for warning in w:
                    assert "does not end with '.nwb'" not in str(warning.message)
    
    def test_data_interface_warning_raised_for_non_nwb_extension(self):
        """Test that a warning is raised when nwbfile_path does not end with .nwb in DataInterface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file path without .nwb extension
            non_nwb_path = Path(temp_dir) / "test_file.txt"
            
            # Check that a warning is raised
            with pytest.warns(UserWarning, match="does not end with '.nwb'"):
                # We don't actually need to run the full conversion, just call the method
                # that checks the file extension
                self.data_interface.run_conversion(
                    nwbfile_path=non_nwb_path,
                    metadata={
                        "NWBFile": {
                            "session_description": "test", 
                            "identifier": "test",
                            "session_start_time": "2023-01-01T12:00:00"
                        }
                    },
                    overwrite=True,
                )

    def test_data_interface_no_warning_for_nwb_extension(self):
        """Test that no warning is raised when nwbfile_path ends with .nwb in DataInterface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file path with .nwb extension
            nwb_path = Path(temp_dir) / "test_file.nwb"
            
            # Check that no warning is raised
            with warnings.catch_warnings(record=True) as w:
                # Filter out other warnings that might be raised
                warnings.filterwarnings("always", category=UserWarning)
                
                # We don't actually need to run the full conversion, just call the method
                # that checks the file extension
                self.data_interface.run_conversion(
                    nwbfile_path=nwb_path,
                    metadata={
                        "NWBFile": {
                            "session_description": "test", 
                            "identifier": "test",
                            "session_start_time": "2023-01-01T12:00:00"
                        }
                    },
                    overwrite=True,
                )
                
                # Check that no warning about file extension was raised
                for warning in w:
                    assert "does not end with '.nwb'" not in str(warning.message)
