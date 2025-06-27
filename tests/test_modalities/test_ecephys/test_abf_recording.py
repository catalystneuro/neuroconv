"""Tests for ABF extracellular recording interface."""

import unittest
from unittest.mock import patch, MagicMock

from neuroconv.datainterfaces import AbfRecordingInterface


class TestAbfRecordingInterface(unittest.TestCase):
    """Test AbfRecordingInterface functionality."""

    def test_interface_import(self):
        """Test that the interface can be imported successfully."""
        self.assertTrue(hasattr(AbfRecordingInterface, 'display_name'))
        self.assertEqual(AbfRecordingInterface.display_name, "ABF Recording")
        self.assertIn(".abf", AbfRecordingInterface.associated_suffixes)

    def test_source_schema(self):
        """Test that the source schema is generated correctly."""
        schema = AbfRecordingInterface.get_source_schema()
        self.assertIn('properties', schema)
        self.assertIn('file_path', schema['properties'])
        self.assertIn('Path to ABF file', schema['properties']['file_path']['description'])

    def test_extractor_name(self):
        """Test that the correct extractor is used."""
        self.assertEqual(AbfRecordingInterface.ExtractorName, "NeoBaseRecordingExtractor")
        self.assertEqual(
            AbfRecordingInterface.ExtractorModuleName,
            "spikeinterface.extractors.neoextractors.neobaseextractor"
        )

    @patch('spikeinterface.extractors.neoextractors.neobaseextractor.NeoBaseRecordingExtractor')
    @patch('pathlib.Path.is_file')
    def test_interface_instantiation(self, mock_is_file, mock_extractor):
        """Test that the interface can be instantiated with mocked extractor."""
        # Mock file existence
        mock_is_file.return_value = True
        
        # Mock the extractor to avoid needing real file
        mock_instance = MagicMock()
        mock_instance.get_channel_ids.return_value = ['0', '1', '2']
        mock_instance.get_property_keys.return_value = []
        mock_instance.get_num_segments.return_value = 1
        mock_extractor.return_value = mock_instance

        # Test instantiation
        interface = AbfRecordingInterface(file_path="/fake/path/test.abf")
        
        # Verify the interface was created
        self.assertIsInstance(interface, AbfRecordingInterface)
        self.assertEqual(str(interface.source_data['file_path']), "/fake/path/test.abf")

    def test_source_data_to_extractor_kwargs(self):
        """Test the conversion of source data to extractor kwargs."""
        # Create a mock interface to test the method
        interface = AbfRecordingInterface.__new__(AbfRecordingInterface)
        
        source_data = {
            'file_path': 'test.abf',
            'stream_id': 'stream1',
            'verbose': True
        }
        
        extractor_kwargs = interface._source_data_to_extractor_kwargs(source_data)
        
        # Should include all source data plus all_annotations
        expected = source_data.copy()
        expected['all_annotations'] = True
        
        self.assertEqual(extractor_kwargs, expected)


if __name__ == '__main__':
    unittest.main()