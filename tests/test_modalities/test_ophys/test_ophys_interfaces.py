import re
import warnings

import numpy as np
import pytest
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

    def test_always_write_timestamps(self, setup_interface):
        # By default the MockImagingInterface has a uniform sampling rate

        nwbfile = self.interface.create_nwbfile(always_write_timestamps=True)
        two_photon_series = nwbfile.acquisition["TwoPhotonSeries"]
        imaging = self.interface.imaging_extractor
        expected_timestamps = imaging.get_timestamps()

        np.testing.assert_array_equal(two_photon_series.timestamps[:], expected_timestamps)

    # Remove this after roiextractors 0.5.10 is released
    def test_all_conversion_checks(self):
        pass


class TestMockSegmentationInterface(SegmentationExtractorInterfaceTestMixin):

    data_interface_cls = MockSegmentationInterface
    interface_kwargs = dict()

    def test_roi_ids_property(self):
        """Test that roi_ids property returns all ROI IDs (cell + background)."""
        interface = MockSegmentationInterface(num_rois=10)
        roi_ids = interface.roi_ids

        expected_cell_ids = interface.segmentation_extractor.get_roi_ids()
        expected_background_ids = interface.segmentation_extractor.get_background_ids()
        expected_all_ids = expected_cell_ids + expected_background_ids
        assert roi_ids == expected_all_ids

    def test_add_to_nwbfile_with_roi_ids_to_add(self):
        """Test that passing roi_ids_to_add filters the ROIs in the output."""
        interface = MockSegmentationInterface(num_rois=10)
        selected_ids = ["roi_0", "roi_2", "roi_5"]

        nwbfile = interface.create_nwbfile(roi_ids_to_add=selected_ids)

        plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]
        assert len(plane_segmentation) == 3
        written_roi_names = list(plane_segmentation["roi_name"].data)
        assert written_roi_names == selected_ids


# This is a temporary test class to show that the migration path to kwargs only works as intended.
# TODO: Remove this test class in June 2026 or after when positional arguments are no longer supported.
class TestMockImagingInterfaceArgsDeprecation:
    """Test the *args deprecation pattern in MockImagingInterface.add_to_nwbfile."""

    def test_add_to_nwbfile_positional_args_trigger_future_warning(self):
        """Test that passing positional arguments to add_to_nwbfile triggers a FutureWarning."""
        interface = MockImagingInterface()
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()

        expected_warning = re.escape(
            "Passing arguments positionally to add_to_nwbfile is deprecated "
            "and will be removed in June 2026 or after. "
            "The following arguments were passed positionally: ['photon_series_type']. "
            "Please use keyword arguments instead."
        )
        with pytest.warns(FutureWarning, match=expected_warning):
            interface.add_to_nwbfile(nwbfile, metadata, "TwoPhotonSeries")

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

    def test_add_to_nwbfile_too_many_positional_args_raises_error(self):
        """Test that passing too many positional arguments to add_to_nwbfile raises TypeError.

        Since *args allows an arbitrary number of positional arguments, we must explicitly
        check and raise TypeError when too many are passed.
        """
        interface = MockImagingInterface()
        metadata = interface.get_metadata()
        nwbfile = mock_NWBFile()

        expected_msg = re.escape(
            "add_to_nwbfile() takes at most 9 positional arguments but 10 were given. "
            "Note: Positional arguments are deprecated and will be removed in June 2026 or after. Please use keyword arguments."
        )
        with pytest.raises(TypeError, match=expected_msg):
            interface.add_to_nwbfile(
                nwbfile, metadata, "TwoPhotonSeries", 0, "acquisition", False, False, "v2", None, "extra"
            )

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
        assert "TwoPhotonSeries" in nwbfile.acquisition

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
        # Verify data was written to processing/ophys
        assert "ophys" in nwbfile.processing
        assert "TwoPhotonSeries" in nwbfile.processing["ophys"].data_interfaces
