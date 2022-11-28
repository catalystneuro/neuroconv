from unittest import TestCase
from datetime import datetime

from pandas import Timedelta

from neuroconv.tools.testing import MockDataInterface


class TestInterfaceTimes(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.interface = MockDataInterface()
        cls.interface.align_to_session_start_time()

    def test_interface_starting_time(self):
        assert self.interface.get_start_time() == datetime(year=2022, month=11, day=28, hour=13, minute=20, second=23)

    def test_interface_relative_starting_time(self):
        assert self.interface.get_relative_start_time() == Timedelta(0)
