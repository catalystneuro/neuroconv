import inspect
import json
import tempfile
from abc import abstractmethod
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Type, Union

import numpy as np
import pytest
from hdmf_zarr import NWBZarrIO
from jsonschema.validators import Draft7Validator, validate
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.testing import check_recordings_equal, check_sortings_equal

from neuroconv import BaseDataInterface, NWBConverter
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
from neuroconv.tools.nwb_helpers import (
    configure_backend,
    get_default_backend_configuration,
)
from neuroconv.utils import _NWBMetaDataEncoder


class DataInterfaceTestMixin:
    """
    Generic class for testing DataInterfaces.


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
    interface_kwargs: dict
    save_directory: Path = Path(tempfile.mkdtemp())
    conversion_options: Optional[dict] = None
    maxDiff = None

    @pytest.fixture
    def setup_interface(self, request):
        """Add this as a fixture when you want freshly created interface in the test."""
        self.test_name: str = ""
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    @pytest.fixture(scope="class", autouse=True)
    def setup_default_conversion_options(self, request):
        cls = request.cls
        cls.conversion_options = cls.conversion_options or dict()
        return cls.conversion_options

    def test_source_schema_valid(self):
        schema = self.data_interface_cls.get_source_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_conversion_options_schema_valid(self):
        schema = self.interface.get_conversion_options_schema()
        Draft7Validator.check_schema(schema=schema)

    def test_metadata_schema_valid(self, setup_interface):
        schema = self.interface.get_metadata_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata(self):
        # Validate metadata now happens on the class itself
        metadata = self.interface.get_metadata()
        self.check_extracted_metadata(metadata)

    def test_no_metadata_mutation(self, setup_interface):
        """Ensure the metadata object is not altered by `add_to_nwbfile` method."""

        nwbfile = mock_NWBFile()

        metadata = self.interface.get_metadata()
        metadata_before_add_method = deepcopy(metadata)

        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **self.conversion_options)
        assert metadata == metadata_before_add_method

    def check_run_conversion_with_backend_configuration(
        self, nwbfile_path: str, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        nwbfile = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        backend_configuration = self.interface.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            metadata=metadata,
            backend_configuration=backend_configuration,
            **self.conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend(
        self, nwbfile_path: str, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        source_data = dict(Test=self.interface_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        metadata = converter.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        conversion_options = dict(Test=self.conversion_options)

        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            conversion_options=conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend_configuration(
        self, nwbfile_path: str, backend: Union["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        source_data = dict(Test=self.interface_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        metadata = converter.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        conversion_options = dict(Test=self.conversion_options)

        nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
        backend_configuration = converter.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            metadata=metadata,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
        )

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

    @pytest.mark.parametrize("backend", ["hdf5", "zarr"])
    def test_run_conversion_with_backend(self, setup_interface, tmp_path, backend):

        nwbfile_path = str(tmp_path / f"conversion_with_backend{backend}-{self.test_name}.nwb")

        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            **self.conversion_options,
        )

        if backend == "zarr":
            with NWBZarrIO(path=nwbfile_path, mode="r") as io:
                io.read()

    @pytest.mark.parametrize("backend", ["hdf5", "zarr"])
    def test_configure_backend_for_equivalent_nwbfiles(self, setup_interface, tmp_path, backend):
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        nwbfile_1 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        nwbfile_2 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile_1, backend=backend)
        configure_backend(nwbfile=nwbfile_2, backend_configuration=backend_configuration)

    def test_all_conversion_checks(self, setup_interface, tmp_path):
        interface, test_name = setup_interface

        # Create a unique test name and file path
        nwbfile_path = str(tmp_path / f"{self.__class__.__name__}_{self.test_name}.nwb")
        self.nwbfile_path = nwbfile_path

        # Now run the checks using the setup objects
        self.check_conversion_options_schema_valid()
        self.check_metadata()

        self.check_run_conversion_in_nwbconverter_with_backend(nwbfile_path=nwbfile_path, backend="hdf5")
        self.check_run_conversion_in_nwbconverter_with_backend_configuration(nwbfile_path=nwbfile_path, backend="hdf5")

        self.check_run_conversion_with_backend_configuration(nwbfile_path=nwbfile_path, backend="hdf5")

        self.check_read_nwb(nwbfile_path=nwbfile_path)

        # Any extra custom checks to run
        self.run_custom_checks()


class TemporalAlignmentMixin:
    """
    Generic class for testing temporal alignment methods.
    """

    data_interface_cls: Type[BaseDataInterface]
    interface_kwargs: dict
    save_directory: Path = Path(tempfile.mkdtemp())
    conversion_options: Optional[dict] = None
    maxDiff = None

    @pytest.fixture
    def setup_interface(self, request):

        self.test_name: str = ""
        self.interface = self.data_interface_cls(**self.interface_kwargs)
        return self.interface, self.test_name

    @pytest.fixture(scope="class", autouse=True)
    def setup_default_conversion_options(self, request):
        cls = request.cls
        cls.conversion_options = cls.conversion_options or dict()
        return cls.conversion_options

    def setUpFreshInterface(self):
        """Protocol for creating a fresh instance of the interface."""
        self.interface = self.data_interface_cls(**self.interface_kwargs)

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

    def test_interface_alignment(self, setup_interface):

        interface, test_name = setup_interface

        self.check_interface_get_original_timestamps()
        self.check_interface_get_timestamps()
        self.check_interface_set_aligned_timestamps()
        self.check_shift_timestamps_by_start_time()
        self.check_interface_original_timestamps_inmutability()

        self.check_nwbfile_temporal_alignment()


class ImagingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls: Type[BaseImagingExtractorInterface]

    def check_read_nwb(self, nwbfile_path: str):
        from roiextractors import NwbImagingExtractor
        from roiextractors.testing import check_imaging_equal

        imaging = self.interface.imaging_extractor
        nwb_imaging = NwbImagingExtractor(file_path=nwbfile_path)

        exclude_channel_comparison = False
        if imaging.get_channel_names() is None:
            exclude_channel_comparison = True

        check_imaging_equal(imaging, nwb_imaging, exclude_channel_comparison)

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory
            / f"{self.data_interface_cls.__name__}_{self.test_name}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.interface_kwargs)

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
        from roiextractors import NwbSegmentationExtractor
        from roiextractors.testing import check_segmentations_equal

        nwb_segmentation = NwbSegmentationExtractor(file_path=nwbfile_path)
        segmentation = self.interface.segmentation_extractor
        check_segmentations_equal(segmentation, nwb_segmentation)


class RecordingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    Generic class for testing any recording interface.
    """

    data_interface_cls: Type[BaseRecordingExtractorInterface]

    def check_read_nwb(self, nwbfile_path: str):
        from spikeinterface.extractors import NwbRecordingExtractor

        recording = self.interface.recording_extractor

        electrical_series_name = self.interface.get_metadata()["Ecephys"][self.interface.es_key]["name"]

        if recording.get_num_segments() == 1:
            # Spikeinterface behavior is to load the electrode table channel_name property as a channel_id
            self.nwb_recording = NwbRecordingExtractor(
                file_path=nwbfile_path,
                electrical_series_name=electrical_series_name,
                use_pynwb=True,
            )

            # Set channel_ids right for comparison
            # Neuroconv ALWAYS writes a string property `channel_name`` to the electrode table.
            # And the NwbRecordingExtractor always uses `channel_name` property as the channel_ids
            # `check_recordings_equal` compares ids so we need to rename the channels or the original recordings
            # So they match
            properties_in_the_recording = recording.get_property_keys()
            if "channel_name" in properties_in_the_recording:
                channel_name = recording.get_property("channel_name").astype("str", copy=False)
            else:
                channel_name = recording.get_channel_ids().astype("str", copy=False)

            recording = recording.rename_channels(new_channel_ids=channel_name)

            # Edge case that only occurs in testing, but should eventually be fixed nonetheless
            # The NwbRecordingExtractor on spikeinterface experiences an issue when duplicated channel_ids
            # are specified, which occurs during check_recordings_equal when there is only one channel
            if self.nwb_recording.get_channel_ids()[0] != self.nwb_recording.get_channel_ids()[-1]:
                check_recordings_equal(RX1=recording, RX2=self.nwb_recording, return_scaled=False)

                # This was added to test probe, we should just compare the probes
                for property_name in ["rel_x", "rel_y", "rel_z"]:
                    if (
                        property_name in properties_in_the_recording
                        or property_name in self.nwb_recording.get_property_keys()
                    ):
                        assert_array_equal(
                            recording.get_property(property_name), self.nwb_recording.get_property(property_name)
                        )
                if recording.has_scaled_traces() and self.nwb_recording.has_scaled_traces():
                    check_recordings_equal(RX1=recording, RX2=self.nwb_recording, return_scaled=True)

            # Compare channel groups
            # Neuroconv ALWAYS writes a string property `group_name` to the electrode table.
            # The NwbRecordingExtractor takes the `group_name` from the electrode table and sets it `group` property
            if "group_name" in properties_in_the_recording:
                group_name_array = recording.get_property("group_name").astype("str", copy=False)
            elif "group" in properties_in_the_recording:
                group_name_array = recording.get_property("group").astype("str", copy=False)
            else:
                default_group_name = "ElectrodeGroup"
                group_name_array = np.full(channel_name.size, fill_value=default_group_name)

            group_names_in_nwb = self.nwb_recording.get_property("group")
            np.testing.assert_array_equal(group_name_array, group_names_in_nwb)

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
            with pytest.raises(
                AssertionError,
                match="This recording has multiple segments; please use 'align_segment_timestamps' instead.",
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
            with pytest.raises(
                AssertionError,
                match="This recording has multiple segments; please use 'align_segment_timestamps' instead.",
            ):
                all_pre_alignment_timestamps = self.interface.get_original_timestamps()

                all_aligned_timestamps = [
                    unaligned_timestamps + 1.23 for unaligned_timestamps in all_pre_alignment_timestamps
                ]
                self.interface.set_aligned_timestamps(aligned_timestamps=all_aligned_timestamps)

    def test_interface_alignment(self, setup_interface):

        interface, test_name = setup_interface

        self.check_interface_get_original_timestamps()
        self.check_interface_get_timestamps()
        self.check_interface_set_aligned_timestamps()
        self.check_shift_timestamps_by_start_time()
        self.check_interface_original_timestamps_inmutability()

        self.check_interface_set_aligned_segment_timestamps()
        self.check_shift_timestamps_by_start_time()
        self.check_shift_segment_timestamps_by_starting_times()

        self.check_nwbfile_temporal_alignment()


class SortingExtractorInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls: Type[BaseSortingExtractorInterface]
    associated_recording_cls: Optional[Type[BaseRecordingExtractorInterface]] = None
    associated_recording_kwargs: Optional[dict] = None

    def setUpFreshInterface(self):
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        recording_interface = self.associated_recording_cls(**self.associated_recording_kwargs)
        self.interface.register_recording(recording_interface=recording_interface)

    def check_read_nwb(self, nwbfile_path: str):
        from spikeinterface.extractors import NwbSortingExtractor

        sorting = self.interface.sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sorting.set_sampling_frequency(30_000.0)

        # NWBSortingExtractor on spikeinterface does not yet support loading data written from multiple segment.
        if sorting.get_num_segments() == 1:
            # TODO after 0.100 release remove this if
            signature = inspect.signature(NwbSortingExtractor)
            if "t_start" in signature.parameters:
                nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf, t_start=0.0)
            else:
                nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf)
            # In the NWBSortingExtractor, since unit_names could be not unique,
            # table "ids" are loaded as unit_ids. Here we rename the original sorting accordingly
            if "unit_name" in sorting.get_property_keys():
                renamed_unit_ids = sorting.get_property("unit_name")
                # sorting_renamed = sorting.rename_units(new_unit_ids=renamed_unit_ids)  #TODO after 0.100 release use this
                sorting_renamed = sorting.select_units(unit_ids=sorting.unit_ids, renamed_unit_ids=renamed_unit_ids)

            else:
                nwb_has_ids_as_strings = all(isinstance(id, str) for id in nwb_sorting.unit_ids)
                if nwb_has_ids_as_strings:
                    renamed_unit_ids = sorting.get_unit_ids()
                    renamed_unit_ids = [str(id) for id in renamed_unit_ids]
                else:
                    renamed_unit_ids = np.arange(len(sorting.unit_ids))

                # sorting_renamed = sorting.rename_units(new_unit_ids=sorting.unit_ids) #TODO after 0.100 release use this
                sorting_renamed = sorting.select_units(unit_ids=sorting.unit_ids, renamed_unit_ids=renamed_unit_ids)
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

    def test_all_conversion_checks(self, setup_interface, tmp_path):
        # The fixture `setup_interface` sets up the necessary objects
        interface, test_name = setup_interface

        # Create a unique test name and file path
        nwbfile_path = str(tmp_path / f"{self.__class__.__name__}_{self.test_name}.nwb")

        # Now run the checks using the setup objects
        self.check_conversion_options_schema_valid()
        self.check_metadata()

        self.check_run_conversion_in_nwbconverter_with_backend(nwbfile_path=nwbfile_path, backend="hdf5")
        self.check_run_conversion_in_nwbconverter_with_backend_configuration(nwbfile_path=nwbfile_path, backend="hdf5")

        self.check_run_conversion_with_backend_configuration(nwbfile_path=nwbfile_path, backend="hdf5")

        self.check_read_nwb(nwbfile_path=nwbfile_path)

        # Any extra custom checks to run
        self.run_custom_checks()

    def test_interface_alignment(self, setup_interface):

        # TODO sorting can have times without associated recordings, test this later
        if self.associated_recording_cls is None:
            return None

        # Skip get_original_timestamps() checks since unsupported
        self.check_interface_get_timestamps()
        self.check_interface_set_aligned_timestamps()
        self.check_interface_set_aligned_segment_timestamps()
        self.check_shift_timestamps_by_start_time()
        self.check_shift_segment_timestamps_by_starting_times()

        self.check_nwbfile_temporal_alignment()


class AudioInterfaceTestMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixin for testing Audio interfaces.
    """

    # Currently asserted in the downstream testing suite; could be refactored in future PR
    def check_read_nwb(self, nwbfile_path: str):
        pass

    # Currently asserted in the downstream testing suite
    def test_interface_alignment(self):
        pass


class DeepLabCutInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixin for testing DeepLabCut interfaces.
    """

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
    """
    A mixin for testing Video interfaces.
    """

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            video_type = Path(self.interface_kwargs["file_paths"][0]).suffix[1:]
            assert f"Video video_{video_type}" in nwbfile.acquisition

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

        aligned_segment_starting_times = [
            1.23 * file_path_index for file_path_index in range(len(self.interface_kwargs))
        ]
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


class MedPCInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixin for testing MedPC interfaces.
    """

    def test_metadata_schema_valid(self):
        pass

    def test_run_conversion_with_backend(self):
        pass

    def test_no_metadata_mutation(self):
        pass

    def test_configure_backend_for_equivalent_nwbfiles(self):
        pass

    def check_metadata_schema_valid(self):
        schema = self.interface.get_metadata_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata(self):
        schema = self.interface.get_metadata_schema()
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        # handle json encoding of datetimes and other tricky types
        metadata_for_validation = json.loads(json.dumps(metadata, cls=_NWBMetaDataEncoder))
        validate(metadata_for_validation, schema)
        self.check_extracted_metadata(metadata)

    def check_no_metadata_mutation(self, metadata: dict):
        """Ensure the metadata object was not altered by `add_to_nwbfile` method."""

        metadata_in = deepcopy(metadata)

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **self.conversion_options)

        assert metadata == metadata_in

    def check_run_conversion_with_backend(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            **self.conversion_options,
        )

    def check_configure_backend_for_equivalent_nwbfiles(
        self, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        nwbfile_1 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        nwbfile_2 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile_1, backend=backend)
        configure_backend(nwbfile=nwbfile_2, backend_configuration=backend_configuration)

    def check_run_conversion_with_backend_configuration(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        nwbfile = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        backend_configuration = self.interface.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            metadata=metadata,
            backend_configuration=backend_configuration,
            **self.conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        test_kwargs = self.test_kwargs[0] if isinstance(self.test_kwargs, list) else self.test_kwargs
        source_data = dict(Test=test_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        conversion_options = dict(Test=self.conversion_options)
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            conversion_options=conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend_configuration(
        self, nwbfile_path: str, metadata: dict, backend: Union["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        test_kwargs = self.test_kwargs[0] if isinstance(self.test_kwargs, list) else self.test_kwargs
        source_data = dict(Test=test_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        conversion_options = dict(Test=self.conversion_options)

        nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
        backend_configuration = converter.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            metadata=metadata,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
        )

    def test_all_conversion_checks(self, metadata: dict):
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

                self.check_no_metadata_mutation(metadata=metadata)

                self.check_configure_backend_for_equivalent_nwbfiles(metadata=metadata)

                self.check_run_conversion_in_nwbconverter_with_backend(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )
                self.check_run_conversion_in_nwbconverter_with_backend_configuration(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )

                self.check_run_conversion_with_backend(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )
                self.check_run_conversion_with_backend_configuration(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )

                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                # TODO: enable when all H5DataIO prewraps are gone
                # self.nwbfile_path = str(self.save_directory / f"{self.__class__.__name__}_{num}.nwb.zarr")
                # self.check_run_conversion(nwbfile_path=self.nwbfile_path, backend="zarr")
                # self.check_run_conversion_custom_backend(nwbfile_path=self.nwbfile_path, backend="zarr")
                # self.check_basic_zarr_read(nwbfile_path=self.nwbfile_path)

                # Any extra custom checks to run
                self.run_custom_checks()

    def check_interface_get_original_timestamps(self, medpc_name_to_info_dict: dict):
        """
        Just to ensure each interface can call .get_original_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        original_timestamps_dict = self.interface.get_original_timestamps(
            medpc_name_to_info_dict=medpc_name_to_info_dict
        )
        for name in self.interface.source_data["aligned_timestamp_names"]:
            original_timestamps = original_timestamps_dict[name]
            assert len(original_timestamps) != 0, f"Timestamps for {name} are empty."

    def check_interface_get_timestamps(self):
        """
        Just to ensure each interface can call .get_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        timestamps_dict = self.interface.get_timestamps()
        for timestamps in timestamps_dict.values():
            assert len(timestamps) != 0

    def check_interface_set_aligned_timestamps(self, medpc_name_to_info_dict: dict):
        """Ensure that internal mechanisms for the timestamps getter/setter work as expected."""
        self.setUpFreshInterface()
        unaligned_timestamps_dict = self.interface.get_original_timestamps(
            medpc_name_to_info_dict=medpc_name_to_info_dict
        )

        random_number_generator = np.random.default_rng(seed=0)
        aligned_timestamps_dict = {}
        for name, unaligned_timestamps in unaligned_timestamps_dict.items():
            aligned_timestamps = (
                unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            )
            aligned_timestamps_dict[name] = aligned_timestamps
        self.interface.set_aligned_timestamps(aligned_timestamps_dict=aligned_timestamps_dict)

        retrieved_aligned_timestamps = self.interface.get_timestamps()
        for name, aligned_timestamps in aligned_timestamps_dict.items():
            assert_array_equal(retrieved_aligned_timestamps[name], aligned_timestamps)

    def check_shift_timestamps_by_start_time(self, medpc_name_to_info_dict: dict):
        """Ensure that internal mechanisms for shifting timestamps by a starting time work as expected."""
        self.setUpFreshInterface()
        unaligned_timestamps_dict = self.interface.get_original_timestamps(
            medpc_name_to_info_dict=medpc_name_to_info_dict
        )

        aligned_starting_time = 1.23
        self.interface.set_aligned_starting_time(
            aligned_starting_time=aligned_starting_time,
            medpc_name_to_info_dict=medpc_name_to_info_dict,
        )

        aligned_timestamps = self.interface.get_timestamps()
        expected_timestamps_dict = {
            name: unaligned_timestamps + aligned_starting_time
            for name, unaligned_timestamps in unaligned_timestamps_dict.items()
        }
        for name, expected_timestamps in expected_timestamps_dict.items():
            assert_array_equal(aligned_timestamps[name], expected_timestamps)

    def check_interface_original_timestamps_inmutability(self, medpc_name_to_info_dict: dict):
        """Check aligning the timestamps for the interface does not change the value of .get_original_timestamps()."""
        self.setUpFreshInterface()
        pre_alignment_original_timestamps_dict = self.interface.get_original_timestamps(
            medpc_name_to_info_dict=medpc_name_to_info_dict
        )

        aligned_timestamps_dict = {
            name: pre_alignment_og_timestamps + 1.23
            for name, pre_alignment_og_timestamps in pre_alignment_original_timestamps_dict.items()
        }
        self.interface.set_aligned_timestamps(aligned_timestamps_dict=aligned_timestamps_dict)

        post_alignment_original_timestamps_dict = self.interface.get_original_timestamps(
            medpc_name_to_info_dict=medpc_name_to_info_dict
        )
        for name, post_alignment_original_timestamps_dict in post_alignment_original_timestamps_dict.items():
            assert_array_equal(post_alignment_original_timestamps_dict, pre_alignment_original_timestamps_dict[name])

    def test_interface_alignment(self, medpc_name_to_info_dict: dict):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                self.check_interface_get_original_timestamps(medpc_name_to_info_dict=medpc_name_to_info_dict)
                self.check_interface_get_timestamps()
                self.check_interface_set_aligned_timestamps(medpc_name_to_info_dict=medpc_name_to_info_dict)
                self.check_shift_timestamps_by_start_time(medpc_name_to_info_dict=medpc_name_to_info_dict)
                self.check_interface_original_timestamps_inmutability(medpc_name_to_info_dict=medpc_name_to_info_dict)

                self.check_nwbfile_temporal_alignment()


class MiniscopeImagingInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixin for testing Miniscope Imaging interfaces.
    """

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_miniscope import Miniscope

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


class ScanImageSinglePlaneImagingInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixing for testing ScanImage Single Plane Imaging interfaces.
    """

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert self.imaging_plane_name in nwbfile.imaging_planes
            assert self.photon_series_name in nwbfile.acquisition
            photon_series_suffix = self.photon_series_name.replace("TwoPhotonSeries", "")
            assert self.interface.two_photon_series_name_suffix == photon_series_suffix
            two_photon_series = nwbfile.acquisition[self.photon_series_name]
            assert two_photon_series.data.shape == self.expected_two_photon_series_data_shape
            assert two_photon_series.unit == "n.a."
            assert two_photon_series.data.dtype == np.int16
            assert two_photon_series.rate is None
            assert two_photon_series.starting_time is None

            imaging_extractor = self.interface.imaging_extractor
            times_from_extractor = imaging_extractor._times
            assert_array_equal(two_photon_series.timestamps[:], times_from_extractor)

            data_from_extractor = imaging_extractor.get_video()
            assert_array_equal(two_photon_series.data[:], data_from_extractor.transpose(0, 2, 1))

            assert two_photon_series.description == json.dumps(self.interface.image_metadata)

            optical_channels = nwbfile.imaging_planes[self.imaging_plane_name].optical_channel
            optical_channel_names = [channel.name for channel in optical_channels]
            assert self.interface_kwargs["channel_name"] in optical_channel_names
            assert len(optical_channels) == 1


class ScanImageMultiPlaneImagingInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """
    A mixin for testing ScanImage MultiPlane Imaging interfaces.
    """

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert self.imaging_plane_name in nwbfile.imaging_planes
            assert self.photon_series_name in nwbfile.acquisition
            photon_series_suffix = self.photon_series_name.replace("TwoPhotonSeries", "")
            assert self.interface.two_photon_series_name_suffix == photon_series_suffix
            two_photon_series = nwbfile.acquisition[self.photon_series_name]
            assert two_photon_series.data.shape == self.expected_two_photon_series_data_shape
            assert two_photon_series.unit == "n.a."
            assert two_photon_series.data.dtype == np.int16

            assert two_photon_series.rate == self.expected_rate
            assert two_photon_series.starting_time == self.expected_starting_time
            assert two_photon_series.timestamps is None

            imaging_extractor = self.interface.imaging_extractor
            data_from_extractor = imaging_extractor.get_video()
            assert_array_equal(two_photon_series.data[:], data_from_extractor.transpose(0, 2, 1, 3))

            assert two_photon_series.description == json.dumps(imaging_extractor._imaging_extractors[0].metadata)

            optical_channels = nwbfile.imaging_planes[self.imaging_plane_name].optical_channel
            optical_channel_names = [channel.name for channel in optical_channels]
            assert self.interface_kwargs["channel_name"] in optical_channel_names
            assert len(optical_channels) == 1


class TDTFiberPhotometryInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """Mixin for testing TDT Fiber Photometry interfaces."""

    def test_metadata_schema_valid(self):
        pass

    def test_no_metadata_mutation(self):
        pass

    def test_run_conversion_with_backend(self):
        pass

    def test_no_metadata_mutation(self):
        pass

    def test_configure_backend_for_equivalent_nwbfiles(self):
        pass

    def check_metadata_schema_valid(self):
        schema = self.interface.get_metadata_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_no_metadata_mutation(self, metadata: dict):
        """Ensure the metadata object was not altered by `add_to_nwbfile` method."""

        metadata_in = deepcopy(metadata)

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **self.conversion_options)

        assert metadata == metadata_in

    def check_run_conversion_with_backend(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            **self.conversion_options,
        )

    def check_configure_backend_for_equivalent_nwbfiles(
        self, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        nwbfile_1 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        nwbfile_2 = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)

        backend_configuration = get_default_backend_configuration(nwbfile=nwbfile_1, backend=backend)
        configure_backend(nwbfile=nwbfile_2, backend_configuration=backend_configuration)

    def check_run_conversion_with_backend_configuration(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        nwbfile = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)
        backend_configuration = self.interface.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            backend_configuration=backend_configuration,
            **self.conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend(
        self, nwbfile_path: str, metadata: dict, backend: Literal["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        test_kwargs = self.test_kwargs[0] if isinstance(self.test_kwargs, list) else self.test_kwargs
        source_data = dict(Test=test_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        conversion_options = dict(Test=self.conversion_options)
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            conversion_options=conversion_options,
        )

    def check_run_conversion_in_nwbconverter_with_backend_configuration(
        self, nwbfile_path: str, metadata: dict, backend: Union["hdf5", "zarr"] = "hdf5"
    ):
        class TestNWBConverter(NWBConverter):
            data_interface_classes = dict(Test=type(self.interface))

        test_kwargs = self.test_kwargs[0] if isinstance(self.test_kwargs, list) else self.test_kwargs
        source_data = dict(Test=test_kwargs)
        converter = TestNWBConverter(source_data=source_data)

        conversion_options = dict(Test=self.conversion_options)

        nwbfile = converter.create_nwbfile(metadata=metadata, conversion_options=conversion_options)
        backend_configuration = converter.get_default_backend_configuration(nwbfile=nwbfile, backend=backend)
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            overwrite=True,
            metadata=metadata,
            backend_configuration=backend_configuration,
            conversion_options=conversion_options,
        )

    def test_all_conversion_checks(self, metadata: dict):
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

                self.check_no_metadata_mutation(metadata=metadata)

                self.check_configure_backend_for_equivalent_nwbfiles(metadata=metadata)

                self.check_run_conversion_in_nwbconverter_with_backend(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )
                self.check_run_conversion_in_nwbconverter_with_backend_configuration(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )

                self.check_run_conversion_with_backend(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )
                self.check_run_conversion_with_backend_configuration(
                    nwbfile_path=self.nwbfile_path, metadata=metadata, backend="hdf5"
                )

                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                # TODO: enable when all H5DataIO prewraps are gone
                # self.nwbfile_path = str(self.save_directory / f"{self.__class__.__name__}_{num}.nwb.zarr")
                # self.check_run_conversion(nwbfile_path=self.nwbfile_path, backend="zarr")
                # self.check_run_conversion_custom_backend(nwbfile_path=self.nwbfile_path, backend="zarr")
                # self.check_basic_zarr_read(nwbfile_path=self.nwbfile_path)

                # Any extra custom checks to run
                self.run_custom_checks()

    def check_interface_get_original_timestamps(self):
        """
        Just to ensure each interface can call .get_original_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        stream_name_to_timestamps = self.interface.get_original_timestamps(t1=t1, t2=t2)
        for stream_name, timestamps in stream_name_to_timestamps.items():
            assert len(timestamps) != 0, f"Timestamps for {stream_name} are empty."

    def check_interface_get_timestamps(self):
        """
        Just to ensure each interface can call .get_timestamps() without an error raising.

        Also, that it always returns non-empty.
        """
        self.setUpFreshInterface()
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        stream_name_to_timestamps = self.interface.get_timestamps(t1=t1, t2=t2)
        for stream_name, timestamps in stream_name_to_timestamps.items():
            assert len(timestamps) != 0, f"Timestamps for {stream_name} are empty."

    def check_interface_set_aligned_timestamps(self):
        """Ensure that internal mechanisms for the timestamps getter/setter work as expected."""
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        self.setUpFreshInterface()
        unaligned_stream_name_to_timestamps = self.interface.get_original_timestamps(t1=t1, t2=t2)

        random_number_generator = np.random.default_rng(seed=0)
        aligned_stream_name_to_timestamps = {}
        for stream_name, unaligned_timestamps in unaligned_stream_name_to_timestamps.items():
            aligned_timestamps = (
                unaligned_timestamps + 1.23 + random_number_generator.random(size=unaligned_timestamps.shape)
            )
            aligned_stream_name_to_timestamps[stream_name] = aligned_timestamps
        self.interface.set_aligned_timestamps(stream_name_to_aligned_timestamps=aligned_stream_name_to_timestamps)
        t1 += 1.23 if t1 != 0.0 else 0.0
        t2 += 2.23 if t2 != 0.0 else 0.0

        retrieved_aligned_stream_name_to_timestamps = self.interface.get_timestamps(t1=t1, t2=t2)
        for stream_name, aligned_timestamps in aligned_stream_name_to_timestamps.items():
            retrieved_aligned_timestamps = retrieved_aligned_stream_name_to_timestamps[stream_name]
            assert_array_equal(retrieved_aligned_timestamps, aligned_timestamps)

    def check_shift_timestamps_by_start_time(self):
        """Ensure that internal mechanisms for shifting timestamps by a starting time work as expected."""
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        self.setUpFreshInterface()
        unaligned_stream_name_to_timestamps = self.interface.get_original_timestamps(t1=t1, t2=t2)

        aligned_starting_time = 1.23
        self.interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time, t1=t1, t2=t2)
        t1 += aligned_starting_time if t1 != 0.0 else 0.0
        t2 += aligned_starting_time if t2 != 0.0 else 0.0

        aligned_stream_name_to_timestamps = self.interface.get_timestamps(t1=t1, t2=t2)
        expected_timestamps_dict = {
            name: unaligned_timestamps + aligned_starting_time
            for name, unaligned_timestamps in unaligned_stream_name_to_timestamps.items()
        }
        for name, expected_timestamps in expected_timestamps_dict.items():
            timestamps = aligned_stream_name_to_timestamps[name]
            assert_array_equal(timestamps, expected_timestamps)

    def check_interface_original_timestamps_inmutability(self):
        """Check aligning the timestamps for the interface does not change the value of .get_original_timestamps()."""
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        self.setUpFreshInterface()
        pre_alignment_stream_name_to_timestamps = self.interface.get_original_timestamps(t1=t1, t2=t2)

        aligned_stream_name_to_timestamps = {
            name: pre_alignment_timestamps + 1.23
            for name, pre_alignment_timestamps in pre_alignment_stream_name_to_timestamps.items()
        }
        self.interface.set_aligned_timestamps(stream_name_to_aligned_timestamps=aligned_stream_name_to_timestamps)

        post_alignment_stream_name_to_timestamps = self.interface.get_original_timestamps(t1=t1, t2=t2)
        for name, post_alignment_timestamps in post_alignment_stream_name_to_timestamps.items():
            pre_alignment_timestamps = pre_alignment_stream_name_to_timestamps[name]
            assert_array_equal(post_alignment_timestamps, pre_alignment_timestamps)

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
