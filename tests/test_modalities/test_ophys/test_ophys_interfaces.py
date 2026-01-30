import warnings

import numpy as np
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
    SegmentationExtractorInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import (
    MockImagingInterface,
    MockSegmentationInterface,
)


class TestMockImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = MockImagingInterface
    interface_kwargs = dict()
    optical_series_name = "MicroscopySeries"  # Override default for new metadata structure

    def test_always_write_timestamps(self, setup_interface):
        # By default the MockImagingInterface has a uniform sampling rate

        nwbfile = self.interface.create_nwbfile(always_write_timestamps=True)
        # New API uses "MicroscopySeries" as the default name for photon series
        microscopy_series = nwbfile.acquisition["MicroscopySeries"]
        imaging = self.interface.imaging_extractor
        expected_timestamps = imaging.get_timestamps()

        np.testing.assert_array_equal(microscopy_series.timestamps[:], expected_timestamps)

    # Remove this after roiextractors 0.5.10 is released
    def test_all_conversion_checks(self):
        pass


class TestMockSegmentationInterface(SegmentationExtractorInterfaceTestMixin):

    data_interface_cls = MockSegmentationInterface
    interface_kwargs = dict()


# Tests for MockImagingInterface conversion options
class TestMockImagingInterfaceConversion:
    """Test MockImagingInterface add_to_nwbfile with keyword-only arguments."""

    def test_add_to_nwbfile_keyword_args_no_future_warning(self):
        """Test that passing keyword arguments to add_to_nwbfile does not trigger FutureWarning."""
        interface = MockImagingInterface()
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, stub_test=True)

        future_warnings = [w for w in caught_warnings if issubclass(w.category, FutureWarning)]
        assert len(future_warnings) == 0

    def test_create_nwbfile_keyword_args_no_future_warning(self):
        """Test that create_nwbfile with keyword arguments does not trigger positional args FutureWarning."""
        interface = MockImagingInterface()

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            nwbfile = interface.create_nwbfile(stub_test=True)

        positional_arg_warnings = [
            w for w in caught_warnings if issubclass(w.category, FutureWarning) and "positionally" in str(w.message)
        ]
        assert len(positional_arg_warnings) == 0
        # New API uses "MicroscopySeries" as the default name
        assert "MicroscopySeries" in nwbfile.acquisition

    def test_create_nwbfile_passes_conversion_options_as_keywords(self):
        """Test that create_nwbfile passes conversion options as keywords to add_to_nwbfile."""
        interface = MockImagingInterface()

        # Test with multiple conversion options to verify they are passed correctly
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            nwbfile = interface.create_nwbfile(stub_test=True, parent_container="processing/ophys")

        positional_arg_warnings = [
            w for w in caught_warnings if issubclass(w.category, FutureWarning) and "positionally" in str(w.message)
        ]
        assert len(positional_arg_warnings) == 0
        # Verify data was written to processing/ophys with new MicroscopySeries name
        assert "ophys" in nwbfile.processing
        assert "MicroscopySeries" in nwbfile.processing["ophys"].data_interfaces
