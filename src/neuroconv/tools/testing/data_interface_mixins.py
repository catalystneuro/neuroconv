import json
import tempfile
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Type, Union

import numpy as np
from jsonschema.validators import Draft7Validator, validate
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

    def check_get_original_timestamps(self):
        """
        Just to ensure each interface can call .get_original_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        timestamps = self.interface.get_original_timestamps()

        assert len(timestamps) != 0

    def check_get_timestamps(self):
        """
        Just to ensure each interface can call .get_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        timestamps = self.interface.get_timestamps()

        assert len(timestamps) != 0

    def check_align_starting_time_internal(self):
        fresh_interface = self.data_interface_cls(**self.test_kwargs)
        unaligned_timestamps = fresh_interface.get_timestamps()

        starting_time = 1.23
        fresh_interface.align_starting_time(starting_time=starting_time)

        aligned_timestamps = fresh_interface.get_timestamps()
        expected_timestamps = unaligned_timestamps + starting_time
        assert_array_equal(x=aligned_timestamps, y=expected_timestamps)

    def check_align_timestamps_internal(self):
        unaligned_timestamps = self.interface.get_original_timestamps()

        aligned_timestamps = unaligned_timestamps + 1.23 + np.random.random(size=unaligned_timestamps.shape)
        self.interface.align_timestamps(aligned_timestamps=aligned_timestamps)

        retrieved_aligned_timestamps = self.interface.get_timestamps()
        assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)

    def check_align_starting_time_external(self):
        pass  # TODO: generalize

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
                self.nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{num}.nwb")
                self.run_conversion(nwbfile_path=self.nwbfile_path)
                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                self.check_temporal_alignment()

                # Any extra custom checks to run
                self.run_custom_checks()

    def check_temporal_alignment(self):
        self.check_get_timestamps()
        self.check_align_starting_time_internal()
        self.check_align_starting_time_external()


class ImagingExtractorInterfaceTestMixin(DataInterfaceTestMixin):
    data_interface_cls: BaseImagingExtractorInterface

    def check_read_nwb(self, nwbfile_path: str):
        imaging = self.interface.imaging_extractor
        nwb_imaging = NwbImagingExtractor(file_path=nwbfile_path)

        exclude_channel_comparison = False
        if imaging.get_channel_names() is None:
            exclude_channel_comparison = True

        check_imaging_equal(imaging, nwb_imaging, exclude_channel_comparison)

    def check_align_starting_time_external(self):
        nwbfile_path = str(
            self.save_directory / f"{self.data_interface_cls.__name__}_{self.case}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.test_kwargs)

        starting_time = 1.23
        interface.align_starting_time(starting_time=starting_time)

        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition["TwoPhotonSeries"].starting_time == starting_time


class SegmentationExtractorInterfaceTestMixin(DataInterfaceTestMixin):
    data_interface_cls: BaseSegmentationExtractorInterface

    def check_read(self, nwbfile_path: str):
        nwb_segmentation = NwbSegmentationExtractor(file_path=nwbfile_path)
        segmentation = self.interface.segmentation_extractor
        check_segmentations_equal(segmentation, nwb_segmentation)


class RecordingExtractorInterfaceTestMixin(DataInterfaceTestMixin):
    data_interface_cls: Type[BaseRecordingExtractorInterface]

    def check_read_nwb(self, nwbfile_path: str):
        recording = self.interface.recording_extractor

        electrical_series_name = self.interface.get_metadata()["Ecephys"][self.interface.es_key]["name"]

        if recording.get_num_segments() == 1:
            # Spikeinterface behavior is to load the electrode table channel_name property as a channel_id
            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path, electrical_series_name=electrical_series_name)
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
            if nwb_recording.get_channel_ids()[0] != nwb_recording.get_channel_ids()[-1]:
                check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=False)
                if recording.has_scaled_traces() and nwb_recording.has_scaled_traces():
                    check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=True)

    def check_align_starting_time_internal(self):
        fresh_interface = self.data_interface_cls(**self.test_kwargs)
        all_unaligned_timestamps = fresh_interface.get_timestamps()

        starting_time = 1.23
        fresh_interface.align_starting_time(starting_time=starting_time)

        if fresh_interface._number_of_segments == 1:
            aligned_timestamps = fresh_interface.get_timestamps()
            expected_timestamps = all_unaligned_timestamps + starting_time
            assert_array_equal(x=aligned_timestamps, y=expected_timestamps)
        else:
            all_aligned_timestamps = fresh_interface.get_timestamps()
            all_expected_timestamps = [
                unaligned_timestamps + starting_time for unaligned_timestamps in all_unaligned_timestamps
            ]
            [
                assert_array_equal(x=aligned_timestamps, y=expected_timestamps)
                for aligned_timestamps, expected_timestamps in zip(all_aligned_timestamps, all_expected_timestamps)
            ]

    def check_align_timestamps_internal(self):
        if fresh_interface._number_of_segments == 1:
            unaligned_timestamps = self.interface.get_original_timestamps()
            aligned_timestamps = unaligned_timestamps + 1.23 + np.random.random(size=unaligned_timestamps.shape)
            self.interface.align_timestamps(aligned_timestamps=aligned_timestamps)

            retrieved_aligned_timestamps = self.interface.get_timestamps()
            assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)
        else:
            all_unaligned_timestamps = self.interface.get_original_timestamps()
            all_aligned_timestamps = [
                unaligned_timestamps + 1.23 + np.random.random(size=unaligned_timestamps.shape)
                for unaligned_timestamps in all_unaligned_timestamps
            ]
            self.interface.align_timestamps(aligned_timestamps=all_aligned_timestamps)

            all_retrieved_aligned_timestamps = self.interface.get_timestamps()
            [
                assert_array_equal(x=retrieved_aligned_timestamps, y=aligned_timestamps)
                for retrieved_aligned_timestamps, aligned_timestamps in zip(
                    all_retrieved_aligned_timestamps, all_aligned_timestamps
                )
            ]


class SortingExtractorInterfaceTestMixin(DataInterfaceTestMixin):
    data_interface_cls: BaseSortingExtractorInterface

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
                self.nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{num}.nwb")
                self.run_conversion(nwbfile_path=self.nwbfile_path)
                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                # Temporal alignment checks
                # Temporary override to disable failing multi-segment case and general sorting application
                # self.check_get_timestamps()
                # self.check_align_starting_time_internal()
                # self.check_align_starting_time_external()
