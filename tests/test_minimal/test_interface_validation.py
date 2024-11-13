from datetime import datetime

from pynwb import NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.testing.mock_interfaces import (
    MockInterface,
)


def test_conversion_options_validation(tmp_path):

    class InterfaceWithDateTimeConversionOptions(MockInterface):

        def add_to_nwbfile(self, nwbfile: NWBFile, datetime_option: datetime):
            pass

    interface = InterfaceWithDateTimeConversionOptions()
    interface.run_conversion(nwbfile_path=tmp_path, datetime_option=datetime.now())

    converter = ConverterPipe(data_interfaces=[interface])

    converter.run_conversion(nwbfile_path=tmp_path, datetime_option=datetime.now())
