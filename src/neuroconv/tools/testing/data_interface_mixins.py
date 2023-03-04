import json
from abc import abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Union

from jsonschema import validate
from jsonschema.validators import Draft7Validator
from roiextractors import NwbImagingExtractor, NwbSegmentationExtractor
from roiextractors.testing import check_imaging_equal, check_segmentations_equal
from spikeinterface.core.testing import check_recordings_equal
from spikeinterface.extractors import NwbRecordingExtractor

from ...basedatainterface import BaseDataInterface
from ...baseextractorinterface import BaseExtractorInterface
from ...datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from ...datainterfaces.ophys.baseimagingextractorinterface import (
    BaseImagingExtractorInterface,
)
from ...datainterfaces.ophys.basesegmentationextractorinterface import BaseSegmentationExtractorInterface


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


class DataInterfaceTestMixin:
    data_interface_cls: Union[BaseDataInterface, Callable]
    cases: Union[dict, list]
    save_directory: Path

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
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        # handle json encoding of datetimes and other tricky types
        metadata = json.loads(json.dumps(metadata, default=json_serial))
        validate(metadata, schema)

        self.check_extracted_metadata(metadata)

    @abstractmethod
    def run_conversion(self, nwbfile_path: str):
        pass

    @abstractmethod
    def check_read(self, nwbfile_path: str):
        pass

    def check_extracted_metadata(self, metadata: dict):
        pass

    def test_conversion_as_lone_interface(self):
        cases = self.cases
        if isinstance(cases, dict):
            cases = [cases]
        for num, kwargs in enumerate(cases):
            with self.subTest(str(num)):
                self.case_name = str(num)
                self.interface = self.data_interface_cls(**kwargs)

                self.check_metadata_schema_valid()
                self.check_conversion_options_schema_valid()
                self.check_metadata()
                nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{num}.nwb")
                kwargs = self.run_conversion(nwbfile_path)
                self.check_read(nwbfile_path=nwbfile_path)


class ExtractorInterfaceTestMixin(DataInterfaceTestMixin):
    data_interface_cls: BaseExtractorInterface

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

    @abstractmethod
    def check_read(self, nwbfile_path: str):
        pass


class RecordingExtractorInterfaceTestMixin(ExtractorInterfaceTestMixin):
    data_interface_cls: BaseRecordingExtractorInterface

    def check_read(self, nwbfile_path: str):
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


class ImagingExtractorInterfaceTestMixin(ExtractorInterfaceTestMixin):
    data_interface_cls: BaseImagingExtractorInterface

    def check_read(self, nwbfile_path: str):
        imaging = self.interface.imaging_extractor
        nwb_imaging = NwbImagingExtractor(file_path=nwbfile_path)

        exclude_channel_comparison = False
        if imaging.get_channel_names() is None:
            exclude_channel_comparison = True

        check_imaging_equal(imaging, nwb_imaging, exclude_channel_comparison)


class SegmentationExtractorInterfaceTestMixin(ExtractorInterfaceTestMixin):
    data_interface_cls: BaseSegmentationExtractorInterface

    def check_read(self, nwbfile_path: str):
        nwb_segmentation = NwbSegmentationExtractor(file_path=nwbfile_path)
        segmentation = self.interface.segmentation_extractor
        check_segmentations_equal(segmentation, nwb_segmentation)
