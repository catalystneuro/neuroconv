from datetime import datetime

from hdmf.testing import TestCase
from pynwb.testing.mock.file import mock_NWBFile
from numpy.testing import assert_array_almost_equal

from neuroconv.tools.testing import MockSpikeGLXNIDQInterface


class TestMockSpikeGLXNIDQInterface(TestCase):
    maxDiff = None

    def test_current_default_inferred_ttl_times(self):
        interface = MockSpikeGLXNIDQInterface()

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3", "nidq#XA4", "nidq#XA5", "nidq#XA6", "nidq#XA7"]
        inferred_starting_times = list()
        for channel_index, channel_name in enumerate(channel_names):
            inferred_starting_times.append(interface.get_event_times_from_ttl(channel_name=channel_name))

        expected_ttl_times = [[1.0 * (1 + 2 * period) + 0.1 * channel for period in range(3)] for channel in range(8)]
        for channel_index, channel_name in enumerate(channel_names):
            inferred_ttl_times = interface.get_event_times_from_ttl(channel_name=channel_name)
            assert_array_almost_equal(x=inferred_ttl_times, y=expected_ttl_times[channel_index], decimal=4)

    def test_explicit_original_default_inferred_ttl_times(self):
        interface = MockSpikeGLXNIDQInterface(signal_duration=7.0, ttl_times=None, ttl_duration=1.0)

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3", "nidq#XA4", "nidq#XA5", "nidq#XA6", "nidq#XA7"]
        expected_ttl_times = [[1.0 * (1 + 2 * period) + 0.1 * channel for period in range(3)] for channel in range(8)]
        for channel_index, channel_name in enumerate(channel_names):
            inferred_ttl_times = interface.get_event_times_from_ttl(channel_name=channel_name)
            assert_array_almost_equal(x=inferred_ttl_times, y=expected_ttl_times[channel_index], decimal=4)

    def test_custom_inferred_ttl_times(self):
        custom_ttl_times = [[1.2], [3.6], [0.7, 4.5], [5.1]]
        interface = MockSpikeGLXNIDQInterface(ttl_times=custom_ttl_times)

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3"]
        for channel_index, channel_name in enumerate(channel_names):
            inferred_ttl_times = interface.get_event_times_from_ttl(channel_name=channel_name)
            assert_array_almost_equal(x=inferred_ttl_times, y=custom_ttl_times[channel_index], decimal=4)

    def test_mock_metadata(self):
        interface = MockSpikeGLXNIDQInterface()

        metadata = interface.get_metadata()

        expected_ecephys_metadata = {
            "Ecephys": {
                "Device": [
                    {"description": "no description", "name": "DeviceEcephys"},
                    {"description": "no description", "manufacturer": "Imec", "name": "Neuropixel-Imec"},
                ],
                "ElectricalSeriesNIDQ": {
                    "description": "Raw acquisition traces from the NIDQ (.nidq.bin) channels.",
                    "name": "ElectricalSeriesNIDQ",
                },
                "ElectrodeGroup": [
                    {
                        "description": "no description",
                        "device": "DeviceEcephys",
                        "location": "unknown",
                        "name": "ElectrodeGroup",
                    },
                    {
                        "description": "A group representing the NIDQ channels.",
                        "device": "Neuropixel-Imec",
                        "location": "unknown",
                        "name": "NIDQChannelGroup",
                    },
                ],
                "Electrodes": [
                    {"description": "Name of the ElectrodeGroup this electrode is a part of.", "name": "group_name"}
                ],
            }
        }
        self.assertDictEqual(d1=metadata["Ecephys"], d2=expected_ecephys_metadata["Ecephys"])

        expected_start_time = datetime(2020, 11, 3, 10, 35, 10)
        assert metadata["NWBFile"]["session_start_time"] == expected_start_time

    def test_mock_run_conversion(self):
        interface = MockSpikeGLXNIDQInterface()

        metadata = interface.get_metadata()

        nwbfile = mock_NWBFile()
        interface.run_conversion(nwbfile=nwbfile, metadata=metadata)

        assert "Neuropixel-Imec" in nwbfile.devices
        assert "NIDQChannelGroup" in nwbfile.electrode_groups
        assert nwbfile.electrodes.id[:] == [0, 1, 2, 3, 4, 5, 6, 7]
        assert "ElectricalSeriesNIDQ" in nwbfile.acquisition
