import json
import tempfile
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Type, Union

from jsonschema.validators import Draft7Validator, validate

from neuroconv.basedatainterface import BaseDataInterface
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

    def test_conversion_as_lone_interface(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.interface = self.data_interface_cls(**kwargs)
                self.check_metadata_schema_valid()
                self.check_conversion_options_schema_valid()
                self.check_metadata()
                nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{num}.nwb")
                self.run_conversion(nwbfile_path)
                self.check_read_nwb(nwbfile_path=nwbfile_path)
