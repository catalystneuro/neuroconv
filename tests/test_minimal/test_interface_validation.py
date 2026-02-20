from datetime import datetime

from pynwb import NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import (
    MockInterface,
)


def test_conversion_options_validation(tmp_path):

    class InterfaceWithDateTimeConversionOptions(MockInterface):
        "class for testing how a file with datetime object is validated"

        def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None, datetime_option: datetime):
            pass

    interface = InterfaceWithDateTimeConversionOptions()

    nwbfile_path = tmp_path / "interface_test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, datetime_option=datetime.now(), overwrite=True)

    data_interfaces = {"InterfaceWithDateTimeConversionOptions": interface}
    conversion_options = {"InterfaceWithDateTimeConversionOptions": {"datetime_option": datetime.now()}}
    converter = ConverterPipe(data_interfaces=data_interfaces)

    nwbfile_path = tmp_path / "converter_test.nwb"
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_options)


def test_conversion_options_validation_with_type_and_callable(tmp_path):
    """Test that type objects and callables in conversion_options don't break validation.

    This is a regression test for https://github.com/catalystneuro/neuroconv/pull/1667.
    NWB GUIDE passes progress_bar_class (a type) and callback functions nested inside
    iterator_opts dict in conversion_options, which caused TypeError during JSON
    serialization in the validation step.
    """

    class InterfaceWithIteratorOpts(MockInterface):

        def add_to_nwbfile(
            self,
            nwbfile: NWBFile,
            metadata: dict | None,
            iterator_opts: dict | None = None,
        ):
            pass

    class MyProgressBar:
        pass

    def my_callback():
        pass

    iterator_opts = dict(
        display_progress=True,
        progress_bar_class=MyProgressBar,
        progress_bar_options=dict(callback=my_callback),
    )

    interface = InterfaceWithIteratorOpts()

    # Test with type object and callable via interface.run_conversion
    nwbfile_path = tmp_path / "interface_test.nwb"
    interface.run_conversion(
        nwbfile_path=nwbfile_path,
        iterator_opts=iterator_opts,
        overwrite=True,
    )

    # Test with type object and callable via ConverterPipe.run_conversion
    data_interfaces = {"InterfaceWithIteratorOpts": interface}
    conversion_options = {
        "InterfaceWithIteratorOpts": {
            "iterator_opts": iterator_opts,
        }
    }
    converter = ConverterPipe(data_interfaces=data_interfaces)

    nwbfile_path = tmp_path / "converter_test.nwb"
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_options)
