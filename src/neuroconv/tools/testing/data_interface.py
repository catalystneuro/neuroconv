import json
import os
import unittest
from abc import abstractmethod

from datetime import datetime, date
from pathlib import Path
from typing import Dict, Union, Callable

from jsonschema import validate
from jsonschema.validators import Draft7Validator
from spikeinterface.core.testing import check_recordings_equal
from spikeinterface.extractors import NwbRecordingExtractor

from ...basedatainterface import BaseDataInterface
from ...datainterfaces.ecephys.baserecordingextractorinterface import BaseRecordingExtractorInterface


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


class AbstractDataInterfaceTest(unittest.TestCase):
    data_interface_cls: Union[BaseDataInterface, Callable]
    kwargs_cases: dict
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
        # handle json encoding of datetimes and other tricky types
        metadata = json.loads(json.dumps(metadata, default=json_serial))
        validate(metadata, schema)

        self.check_extracted_metadata(metadata)

    @abstractmethod
    def run_conversion(self, nwbfile_path: str):
        pass

    @abstractmethod
    def check_read(self, nwbfile_path: str, **kwargs):
        pass

    def check_extracted_metadata(self, metadata: dict):
        pass

    def test_conversion_as_lone_interface(self):
        for case_name, kwargs in self.kwargs_cases.items():
            with self.subTest(case_name):
                self.case_name = case_name
                self.interface = self.data_interface_cls(**kwargs)

                self.check_metadata_schema_valid()
                self.check_conversion_options_schema_valid()
                self.check_metadata()
                nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{case_name}.nwb")
                kwargs = self.run_conversion(nwbfile_path)
                self.check_read(nwbfile_path=nwbfile_path, **kwargs)


class AbstractRecordingInterfaceTest(AbstractDataInterfaceTest):

    data_interface_cls: BaseRecordingExtractorInterface

    def run_conversion(self, nwbfile_path: str) -> dict:
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        electrical_series_name = metadata["Ecephys"][self.interface.es_key]["name"]
        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        return dict(electrical_series_name=electrical_series_name)

    def check_read(
            self,
            nwbfile_path: str,
            electrical_series_name: str = "ElectricalSeries"
    ):
        recording = self.interface.recording_extractor

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
