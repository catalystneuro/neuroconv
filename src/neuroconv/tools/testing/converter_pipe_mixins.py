import json
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import List, Type, Union

from jsonschema.validators import Draft7Validator, validate

from neuroconv import ConverterPipe
from neuroconv.utils import NWBMetaDataEncoder


class ConverterPipeTestMixin:
    """
    Generic class for testing ConverterPipes.

    This mixin must be paired with unittest.TestCase.

    Several of these tests are required to be run in a specific order. In this case,
    there is a `test_conversion` that calls the `check` functions in
    the appropriate order, after the `interface` has been created. Normally, you might
    expect the `interface` to be simply created in the `setUp` method, but this class
    allows you to specify multiple interface_kwargs.

    Class Attributes
    ----------------
    converter_cls : ConverterPipe
        class, not instance
    converter_kwargs : dict or list
        When it is a dictionary, take these as arguments to the constructor of the
        converter. When it is a list, each element of the list is a dictionary of
        arguments to the constructor. Each dictionary will be tested one at a time.
    save_directory : Path, optional
        Directory where test files should be saved.
    """

    converter_cls: Type[ConverterPipe]
    converter_kwargs: Union[dict, List[dict]]
    save_directory: Path = Path(tempfile.mkdtemp())
    maxDiff = None

    def check_conversion_options_schema_valid(self):
        schema = self.converter.get_conversion_options_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata_schema_valid(self):
        schema = self.converter.get_metadata_schema()
        Draft7Validator.check_schema(schema=schema)

    def check_metadata(self):
        schema = self.converter.get_metadata_schema()
        metadata = self.converter.get_metadata()
        # handle json encoding of datetimes and other tricky types
        metadata_for_validation = json.loads(json.dumps(metadata, cls=NWBMetaDataEncoder))
        validate(metadata_for_validation, schema)
        self.check_extracted_metadata(metadata)

    def run_conversion(self, nwbfile_path: str):
        metadata = self.converter.get_metadata()
        self.converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    @abstractmethod
    def check_read_nwb(self, nwbfile_path: str):
        """Read the produced NWB file and compare it to the converter."""
        pass

    def check_extracted_metadata(self, metadata: dict):
        """Override this method to make assertions about specific extracted metadata values."""
        pass

    def run_custom_checks(self):
        """Override this in child classes to inject additional custom checks."""
        pass

    def test_conversion(self):
        converter_kwargs = self.converter_kwargs
        if isinstance(converter_kwargs, dict):
            converter_kwargs = [converter_kwargs]
        for num, kwargs in enumerate(converter_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs
                self.converter = self.converter_cls(**self.test_kwargs)
                self.check_metadata_schema_valid()
                self.check_conversion_options_schema_valid()
                self.check_metadata()
                self.nwbfile_path = str(self.save_directory / f"{self.converter_cls.__name__}_{num}.nwb")
                self.run_conversion(nwbfile_path=self.nwbfile_path)
                self.check_read_nwb(nwbfile_path=self.nwbfile_path)

                # Any extra custom checks to run
                self.run_custom_checks()
