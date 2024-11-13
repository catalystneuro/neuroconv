from datetime import datetime
from typing import Optional

from pynwb import NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import (
    MockInterface,
)


def test_conversion_options_validation(tmp_path):

    class InterfaceWithDateTimeConversionOptions(MockInterface):
        "class for testing how a file with datetime object is validated"

        def add_to_nwbfile(self, nwbfile: NWBFile, metadata: Optional[dict], datetime_option: datetime):
            pass

    interface = InterfaceWithDateTimeConversionOptions()

    nwbfile_path = tmp_path / "interface_test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, datetime_option=datetime.now(), overwrite=True)

    data_interfaces = {"InterfaceWithDateTimeConversionOptions": interface}
    conversion_options = {"InterfaceWithDateTimeConversionOptions": {"datetime_option": datetime.now()}}
    converter = ConverterPipe(data_interfaces=data_interfaces)

    nwbfile_path = tmp_path / "converter_test.nwb"
    converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, conversion_options=conversion_options)
