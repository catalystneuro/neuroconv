import json
import tempfile
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Type, Union

import numpy as np
from hdmf.testing import TestCase as HDMFTestCase
from jsonschema.validators import Draft7Validator, validate
from ndx_miniscope import Miniscope
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from roiextractors import NwbImagingExtractor, NwbSegmentationExtractor
from roiextractors.testing import check_imaging_equal, check_segmentations_equal
from spikeinterface.core.testing import check_recordings_equal, check_sortings_equal
from spikeinterface.extractors import NwbRecordingExtractor, NwbSortingExtractor

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from neuroconv.datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)
from neuroconv.datainterfaces.ophys.baseimagingextractorinterface import (
    BaseImagingExtractorInterface,
)
from neuroconv.datainterfaces.ophys.basesegmentationextractorinterface import (
    BaseSegmentationExtractorInterface,
)
from neuroconv.utils import NWBMetaDataEncoder


class DataInterfaceTestMixin:
    """
    Generic class for testing DataInterfaces.

    This mixin must be paired with unittest.TestCase.

    Several of these tests are required to be run in a specific order. In this case,
    there is a `test_conversion_as_lone_interface` that calls the `check` functions in
    the appropriate order, after the `interface` has been created. Normally, you might
    expect the `interface` to be simply created in the `setUp` method, but this class
    allows you to specify multiple interface_kwargs.

    Class Attributes
    ----------------
    data_interface_cls : DataInterface
        class, not instance
    interface_kwargs : dict or list
        When it is a dictionary, take these as arguments to the constructor of the
        interface. When it is a list, each element of the list is a dictionary of
        arguments to the constructor. Each dictionary will be tested one at a time.
    save_directory : Path, optional
        Directory where test files should be saved.
    """

    data_interface_cls: Type[BaseDataInterface]
    interface_kwargs: Union[dict, List[dict]]
    save_directory: Path = Path(tempfile.mkdtemp())
    maxDiff = None

    def test_source_schema_valid(self):
        schema = self.data_interface_cls.get_source_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_conversion_options_schema_valid(self):
        schema = self.interface.get_conversion_options_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata_schema_valid(self):
        schema = self.interface.get_metadata_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata(self):
        schema = self.interface.get_metadata_schema()
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        # handle json encoding of datetimes and other tricky types
        metadata_for_validation = json.loads(json.dumps(metadata, cls=NWBMetaDataEncoder))
        validate(metadata_for_validation, schema)
        self.check_extracted_metadata(metadata)

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    @abstractmethod
    def check_read_nwb(self, nwbfile_path: str):
        """Read the produced NWB file and compare it to the interface."""
        pass

    def check_extracted_metadata(self, metadata: dict):
        """Override this method to make assertions about specific extracted metadata values."""
        pass

    def run_custom_checks(self):
        """Override this in child classes to inject additional custom checks."""
        pass

    def test_conversion_as_lone_interface(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs
                self.interface = self.data_interface_cls(**self.test_kwargs)
                self.check_metadata_schema_valid()
                self.check_conversion_options_schema_valid()
                self.check_metadata()
                self.nwbfile_path = str(self.save_directory / f"{self.__class__.__name__}_{num}.nwb")
                self.run_conversion(nwbfile_path=self.nwbfile_path)
                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                # Any extra custom checks to run
                self.run_custom_checks()


class TemporalAlignmentMixin:
    """
    Generic class for testing temporal alignment methods.

    This mixin must be paired with a unittest.TestCase class.
    """

    data_interface_cls: Type[BaseDataInterface]
    interface_kwargs: Union[dict, List[dict]]
    maxDiff = None

    def setUpFreshInterface(self):
        """Protocol for creating a fresh instance of the interface."""
        self.interface = self.data_interface_cls(**self.test_kwargs)

    def check_interface_get_original_timestamps(self):
        """
        Just to ensure each interface can call .get_original_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        original_timestamps = self.interface.get_original_timestamps()

        assert len(original_timestamps) != 0

    def check_interface_get_timestamps(self):
        """
        Just to ensure each interface can call .get_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        timestamps = self.interface.get_timestamps()

        assert len(timestamps) != 0

    def check_interface_set_aligned_timestamps(self):
        """Ensure that internal mechanisms for the timestamps getter/setter work as expected."""
        self.setUpFreshInterface()
        unaligned_timestamps = self.interface.get_timestamps()

        random_number_generator = np.random.default_rng(seed=0)
        aligned_timestamps = (
            unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
        )
        self.interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

        retrieved_aligned_timestamps = self.interface.get_timestamps()
        assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)

    def check_shift_timestamps_by_start_time(self):
        """Ensure that internal mechanisms for shifting timestamps by a starting time work as expected."""
        self.setUpFreshInterface()
        unaligned_timestamps = self.interface.get_timestamps()

        aligned_starting_time = 1.23
        self.interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        aligned_timestamps = self.interface.get_timestamps()
        expected_timestamps = unaligned_timestamps + aligned_starting_time
        assert_array_equal(x=aligned_timestamps, y=expected_timestamps)

    def check_interface_original_timestamps_inmutability(self):
        """Check aligning the timestamps for the interface does not change the value of .get_original_timestamps()."""
        self.setUpFreshInterface()
        pre_alignment_original_timestamps = self.interface.get_original_timestamps()

        aligned_timestamps = pre_alignment_original_timestamps + 1.23
        self.interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

        post_alignment_original_timestamps = self.interface.get_original_timestamps()
        assert_array_equal(x=post_alignment_original_timestamps, y=pre_alignment_original_timestamps)

    def check_nwbfile_temporal_alignment(self):
        """Check the temporally aligned timing information makes it into the NWB file."""
        pass  # TODO: will be easier to add when interface have 'add' methods separate from .run_conversion()

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                self.check_interface_get_original_timestamps()
                self.check_interface_get_timestamps()
                self.check_interface_set_aligned_timestamps()
                self.check_shift_timestamps_by_start_time()
                self.check_interface_original_timestamps_inmutability()

                self.check_nwbfile_temporal_alignment()


class ImagingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls: BaseImagingExtractorInterface

    def check_read_nwb(self, nwbfile_path: str):
        imaging = self.interface.imaging_extractor
        nwb_imaging = NwbImagingExtractor(file_path=nwbfile_path)

        exclude_channel_comparison = False
        if imaging.get_channel_names() is None:
            exclude_channel_comparison = True

        check_imaging_equal(imaging, nwb_imaging, exclude_channel_comparison)

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory / f"{self.data_interface_cls.__name__}_{self.case}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.test_kwargs)

        aligned_starting_time = 1.23
        interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition["TwoPhotonSeries"].starting_time == aligned_starting_time


class SegmentationExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls: BaseSegmentationExtractorInterface

    def check_read(self, nwbfile_path: str):
        nwb_segmentation = NwbSegmentationExtractor(file_path=nwbfile_path)
        segmentation = self.interface.segmentation_extractor
        check_segmentations_equal(segmentation, nwb_segmentation)


class RecordingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    Generic class for testing any recording interface.

    Runs all the basic DataInterface tests as well as temporal alignment tests.

    This mixin must be paired with a hdmf.testing.TestCase class.
    """

    data_interface_cls: Type[BaseRecordingExtractorInterface]

    def check_read_nwb(self, nwbfile_path: str):
        recording = self.interface.recording_extractor

        electrical_series_name = self.interface.get_metadata()["Ecephys"][self.interface.es_key]["name"]

        if recording.get_num_segments() == 1:
            # Spikeinterface behavior is to load the electrode table channel_name property as a channel_id
            self.nwb_recording = NwbRecordingExtractor(
                file_path=nwbfile_path, electrical_series_name=electrical_series_name
            )
            if "channel_name" in recording.get_property_keys():
                renamed_channel_ids = recording.get_property("channel_name")
            else:
                renamed_channel_ids = recording.get_channel_ids().astype("str")
            recording = recording.channel_slice(
                channel_ids=recording.get_channel_ids(), renamed_channel_ids=renamed_channel_ids
            )

            # Edge case that only occurs in testing, but should eventually be fixed nonetheless
            # The NwbRecordingExtractor on spikeinterface experiences an issue when duplicated channel_ids
            # are specified, which occurs during check_recordings_equal when there is only one channel
            if self.nwb_recording.get_channel_ids()[0] != self.nwb_recording.get_channel_ids()[-1]:
                check_recordings_equal(RX1=recording, RX2=self.nwb_recording, return_scaled=False)
                if recording.has_scaled_traces() and self.nwb_recording.has_scaled_traces():
                    check_recordings_equal(RX1=recording, RX2=self.nwb_recording, return_scaled=True)

    def check_interface_set_aligned_timestamps(self):
        self.setUpFreshInterface()

        random_number_generator = np.random.default_rng(seed=0)
        if self.interface._number_of_segments == 1:
            unaligned_timestamps = self.interface.get_timestamps()

            aligned_timestamps = (
                unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            )
            self.interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

            retrieved_aligned_timestamps = self.interface.get_timestamps()
            assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)
        else:
            assert isinstance(
                self, HDMFTestCase
            ), "The RecordingExtractorInterfaceTestMixin must be mixed-in with the TestCase from hdmf.testing!"
            with self.assertRaisesWith(
                exc_type=AssertionError,
                exc_msg="This recording has multiple segments; please use 'align_segment_timestamps' instead.",
            ):
                all_unaligned_timestamps = self.interface.get_timestamps()

                all_aligned_segment_timestamps = [
                    unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
                    for unaligned_timestamps in all_unaligned_timestamps
                ]
                self.interface.set_aligned_timestamps(aligned_timestamps=all_aligned_segment_timestamps)

    def check_interface_set_aligned_segment_timestamps(self):
        self.setUpFreshInterface()

        random_number_generator = np.random.default_rng(seed=0)
        if self.interface._number_of_segments == 1:
            unaligned_timestamps = self.interface.get_timestamps()

            all_aligned_segment_timestamps = [
                unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            ]
            self.interface.set_aligned_segment_timestamps(aligned_segment_timestamps=all_aligned_segment_timestamps)

            retrieved_aligned_timestamps = self.interface.get_timestamps()
            assert_array_equal(x=retrieved_aligned_timestamps, y=all_aligned_segment_timestamps[0])
        else:
            all_unaligned_timestamps = self.interface.get_timestamps()
            all_aligned_segment_timestamps = [
                unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
                for unaligned_timestamps in all_unaligned_timestamps
            ]
            self.interface.set_aligned_segment_timestamps(aligned_segment_timestamps=all_aligned_segment_timestamps)

            all_retrieved_aligned_timestamps = self.interface.get_timestamps()
            for retrieved_aligned_timestamps, aligned_segment_timestamps in zip(
                all_retrieved_aligned_timestamps, all_aligned_segment_timestamps
            ):
                assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_segment_timestamps)

    def check_shift_timestamps_by_start_time(self):
        self.setUpFreshInterface()
        all_unaligned_timestamps = self.interface.get_timestamps()

        aligned_starting_time = 1.23
        self.interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        if self.interface._number_of_segments == 1:
            retrieved_aligned_timestamps = self.interface.get_timestamps()
            expected_timestamps = all_unaligned_timestamps + aligned_starting_time
            assert_array_equal(x=retrieved_aligned_timestamps, y=expected_timestamps)
        else:
            all_retrieved_aligned_timestamps = self.interface.get_timestamps()
            all_expected_timestamps = [
                unaligned_timestamps + aligned_starting_time for unaligned_timestamps in all_unaligned_timestamps
            ]
            for retrieved_aligned_timestamps, expected_timestamps in zip(
                all_retrieved_aligned_timestamps, all_expected_timestamps
            ):
                assert_array_equal(x=retrieved_aligned_timestamps, y=expected_timestamps)

    def check_shift_segment_timestamps_by_starting_times(self):
        self.setUpFreshInterface()

        aligned_segment_starting_times = list(np.arange(float(self.interface._number_of_segments)) + 1.23)
        if self.interface._number_of_segments == 1:
            unaligned_timestamps = self.interface.get_timestamps()

            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=aligned_segment_starting_times
            )

            retrieved_aligned_timestamps = self.interface.get_timestamps()
            expected_aligned_timestamps = unaligned_timestamps + aligned_segment_starting_times[0]
            assert_array_equal(x=retrieved_aligned_timestamps, y=expected_aligned_timestamps)
        else:
            all_unaligned_timestamps = self.interface.get_timestamps()

            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=aligned_segment_starting_times
            )

            all_retrieved_aligned_timestamps = self.interface.get_timestamps()
            all_expected_aligned_timestamps = [
                timestamps + segment_starting_time
                for timestamps, segment_starting_time in zip(all_unaligned_timestamps, aligned_segment_starting_times)
            ]
            for retrieved_aligned_timestamps, expected_aligned_timestamps in zip(
                all_retrieved_aligned_timestamps, all_expected_aligned_timestamps
            ):
                assert_array_equal(x=retrieved_aligned_timestamps, y=expected_aligned_timestamps)

    def check_interface_original_timestamps_inmutability(self):
        """Check aligning the timestamps for the interface does not change the value of .get_original_timestamps()."""
        self.setUpFreshInterface()

        if self.interface._number_of_segments == 1:
            pre_alignment_original_timestamps = self.interface.get_original_timestamps()

            aligned_timestamps = pre_alignment_original_timestamps + 1.23
            self.interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

            post_alignment_original_timestamps = self.interface.get_original_timestamps()
            assert_array_equal(x=post_alignment_original_timestamps, y=pre_alignment_original_timestamps)
        else:
            assert isinstance(
                self, HDMFTestCase
            ), "The RecordingExtractorInterfaceTestMixin must be mixed-in with the TestCase from hdmf.testing!"
            with self.assertRaisesWith(
                exc_type=AssertionError,
                exc_msg="This recording has multiple segments; please use 'align_segment_timestamps' instead.",
            ):
                all_pre_alignement_timestamps = self.interface.get_original_timestamps()

                all_aligned_timestamps = [
                    unaligned_timestamps + 1.23 for unaligned_timestamps in all_pre_alignement_timestamps
                ]
                self.interface.set_aligned_timestamps(aligned_timestamps=all_aligned_timestamps)

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                self.check_interface_get_original_timestamps()
                self.check_interface_get_timestamps()
                self.check_interface_set_aligned_timestamps()
                self.check_interface_set_aligned_segment_timestamps()
                self.check_shift_timestamps_by_start_time()
                self.check_shift_segment_timestamps_by_starting_times()
                self.check_interface_original_timestamps_inmutability()

                self.check_nwbfile_temporal_alignment()


class SortingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls: BaseSortingExtractorInterface
    associated_recording_cls: Optional[BaseRecordingExtractorInterface] = None
    associated_recording_kwargs: Optional[dict] = None

    def setUpFreshInterface(self):
        self.interface = self.data_interface_cls(**self.test_kwargs)

        recording_interface = self.associated_recording_cls(**self.associated_recording_kwargs)
        self.interface.register_recording(recording_interface=recording_interface)

    def check_read_nwb(self, nwbfile_path: str):
        sorting = self.interface.sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sorting.set_sampling_frequency(30_000)

        # NWBSortingExtractor on spikeinterface does not yet support loading data written from multiple segment.
        if sorting.get_num_segments() == 1:
            nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf)
            # In the NWBSortingExtractor, since unit_names could be not unique,
            # table "ids" are loaded as unit_ids. Here we rename the original sorting accordingly
            sorting_renamed = sorting.select_units(
                unit_ids=sorting.unit_ids, renamed_unit_ids=np.arange(len(sorting.unit_ids))
            )
            check_sortings_equal(SX1=sorting_renamed, SX2=nwb_sorting)

    def check_interface_set_aligned_segment_timestamps(self):
        self.setUpFreshInterface()

        if self.interface.sorting_extractor.has_recording():
            random_number_generator = np.random.default_rng(seed=0)
            if self.interface._number_of_segments == 1:
                unaligned_timestamps = self.interface.get_timestamps()

                all_aligned_segment_timestamps = [
                    unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
                ]
                self.interface.set_aligned_segment_timestamps(aligned_segment_timestamps=all_aligned_segment_timestamps)

                retrieved_aligned_timestamps = self.interface.get_timestamps()
                assert_array_equal(x=retrieved_aligned_timestamps, y=all_aligned_segment_timestamps[0])
            else:
                all_unaligned_timestamps = self.interface.get_timestamps()
                all_aligned_segment_timestamps = [
                    unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
                    for unaligned_timestamps in all_unaligned_timestamps
                ]
                self.interface.set_aligned_segment_timestamps(aligned_segment_timestamps=all_aligned_segment_timestamps)

                all_retrieved_aligned_timestamps = self.interface.get_timestamps()
                for retrieved_aligned_timestamps, aligned_segment_timestamps in zip(
                    all_retrieved_aligned_timestamps, all_aligned_segment_timestamps
                ):
                    assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_segment_timestamps)

    def check_shift_segment_timestamps_by_starting_times(self):
        self.setUpFreshInterface()

        aligned_segment_starting_times = list(np.arange(float(self.interface._number_of_segments)) + 1.23)
        if self.interface._number_of_segments == 1:
            unaligned_timestamps = self.interface.get_timestamps()

            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=aligned_segment_starting_times
            )

            retrieved_aligned_timestamps = self.interface.get_timestamps()
            expected_aligned_timestamps = unaligned_timestamps + aligned_segment_starting_times[0]
            assert_array_equal(x=retrieved_aligned_timestamps, y=expected_aligned_timestamps)
        else:
            all_unaligned_timestamps = self.interface.get_timestamps()

            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=aligned_segment_starting_times
            )

            all_retrieved_aligned_timestamps = self.interface.get_timestamps()
            all_expected_aligned_timestamps = [
                segment_timestamps + segment_starting_time
                for segment_timestamps, segment_starting_time in zip(
                    all_unaligned_timestamps, aligned_segment_starting_times
                )
            ]
            for retrieved_aligned_timestamps, expected_aligned_timestamps in zip(
                all_retrieved_aligned_timestamps, all_expected_aligned_timestamps
            ):
                assert_array_equal(x=retrieved_aligned_timestamps, y=expected_aligned_timestamps)

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                if self.associated_recording_cls is None:
                    continue

                # Skip get_original_timestamps() checks since unsupported
                self.check_interface_get_timestamps()
                self.check_interface_set_aligned_timestamps()
                self.check_interface_set_aligned_segment_timestamps()
                self.check_shift_timestamps_by_start_time()
                self.check_shift_segment_timestamps_by_starting_times()

                self.check_nwbfile_temporal_alignment()


class AudioInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    def check_read_nwb(self, nwbfile_path: str):
        pass  # asserted in the testing suite; could be refactored in future PR

    def test_interface_alignment(self):
        pass  # Currently asserted in the testing suite


class DeepLabCutInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    def check_interface_get_original_timestamps(self):
        pass  # TODO in separate PR

    def check_interface_get_timestamps(self):
        pass  # TODO in separate PR

    def check_interface_set_aligned_timestamps(self):
        pass  # TODO in separate PR

    def check_shift_timestamps_by_start_time(self):
        pass  # TODO in separate PR

    def check_interface_original_timestamps_inmutability(self):
        pass  # TODO in separate PR

    def check_nwbfile_temporal_alignment(self):
        pass  # TODO in separate PR


class VideoInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            video_type = Path(self.test_kwargs["file_paths"][0]).suffix[1:]
            assert f"Video: video_{video_type}" in nwbfile.acquisition

    def check_interface_set_aligned_timestamps(self):
        all_unaligned_timestamps = self.interface.get_original_timestamps()

        random_number_generator = np.random.default_rng(seed=0)
        aligned_timestamps = [
            unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            for unaligned_timestamps in all_unaligned_timestamps
        ]
        self.interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

        retrieved_aligned_timestamps = self.interface.get_timestamps()
        assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)

    def check_shift_timestamps_by_start_time(self):
        self.setUpFreshInterface()

        aligned_starting_time = 1.23
        self.interface.set_aligned_timestamps(aligned_timestamps=self.interface.get_original_timestamps())
        self.interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)
        all_aligned_timestamps = self.interface.get_timestamps()

        unaligned_timestamps = self.interface.get_original_timestamps()
        all_expected_timestamps = [timestamps + aligned_starting_time for timestamps in unaligned_timestamps]
        [
            assert_array_equal(x=aligned_timestamps, y=expected_timestamps)
            for aligned_timestamps, expected_timestamps in zip(all_aligned_timestamps, all_expected_timestamps)
        ]

    def check_set_aligned_segment_starting_times(self):
        self.setUpFreshInterface()

        aligned_segment_starting_times = [1.23 * file_path_index for file_path_index in range(len(self.test_kwargs))]
        self.interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)
        all_aligned_timestamps = self.interface.get_timestamps()

        unaligned_timestamps = self.interface.get_original_timestamps()
        all_expected_timestamps = [
            timestamps + segment_starting_time
            for timestamps, segment_starting_time in zip(unaligned_timestamps, aligned_segment_starting_times)
        ]
        for aligned_timestamps, expected_timestamps in zip(all_aligned_timestamps, all_expected_timestamps):
            assert_array_equal(x=aligned_timestamps, y=expected_timestamps)

    def check_interface_original_timestamps_inmutability(self):
        self.setUpFreshInterface()

        all_pre_alignment_original_timestamps = self.interface.get_original_timestamps()

        all_aligned_timestamps = [
            pre_alignment_original_timestamps + 1.23
            for pre_alignment_original_timestamps in all_pre_alignment_original_timestamps
        ]
        self.interface.set_aligned_timestamps(aligned_timestamps=all_aligned_timestamps)

        all_post_alignment_original_timestamps = self.interface.get_original_timestamps()
        for post_alignment_original_timestamps, pre_alignment_original_timestamps in zip(
            all_post_alignment_original_timestamps, all_pre_alignment_original_timestamps
        ):
            assert_array_equal(x=post_alignment_original_timestamps, y=pre_alignment_original_timestamps)

    def check_nwbfile_temporal_alignment(self):
        pass  # TODO in separate PR

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                self.check_interface_get_original_timestamps()
                self.check_interface_get_timestamps()
                self.check_interface_set_aligned_timestamps()
                self.check_shift_timestamps_by_start_time()
                self.check_interface_original_timestamps_inmutability()
                self.check_set_aligned_segment_starting_times()

                self.check_nwbfile_temporal_alignment()


class MiniscopeImagingInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert self.device_name in nwbfile.devices
            device = nwbfile.devices[self.device_name]
            assert isinstance(device, Miniscope)
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_name]
            assert imaging_plane.device.name == self.device_name

            # Check OnePhotonSeries
            assert self.photon_series_name in nwbfile.acquisition
            one_photon_series = nwbfile.acquisition[self.photon_series_name]
            assert one_photon_series.unit == "px"
            assert one_photon_series.data.shape == (15, 752, 480)
            assert one_photon_series.data.dtype == np.uint8
            assert one_photon_series.rate is None
            assert one_photon_series.starting_frame is None
            assert one_photon_series.timestamps.shape == (15,)

            imaging_extractor = self.interface.imaging_extractor
            times_from_extractor = imaging_extractor._times
            assert_array_equal(one_photon_series.timestamps, times_from_extractor)
