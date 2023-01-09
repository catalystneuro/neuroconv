from hdmf.testing import TestCase

from neuroconv.tools.testing import MockSpikeGLXNIDQInterface


class TestMockSpikeGLXNIDQInterface(TestCase):
    def test_current_default_inferred_ttl_times(self):
        interface = MockSpikeGLXNIDQInterface()

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3", "nidq#XA4", "nidq#XA5", "nidq#XA6", "nidq#XA7"]
        inferred_starting_times = list()
        for channel_index, channel_name in enumerate(channel_names):
            inferred_starting_times.append(interface.get_event_starting_times_from_ttl(channel_name=channel_name))

        expected_ttl_times = [[1.0 * (1 + period) + 0.1 * channel for period in range(3)] for channel in range(8)]
        self.assertListEqual(list1=inferred_starting_times, list2=expected_ttl_times)

    def test_explicit_original_default_inferred_ttl_times(self):
        interface = MockSpikeGLXNIDQInterface(signal_duration=7.0, ttl_times=None, ttl_duration=1.0)

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3", "nidq#XA4", "nidq#XA5", "nidq#XA6", "nidq#XA7"]
        inferred_starting_times = list()
        for channel_index, channel_name in enumerate(channel_names):
            inferred_starting_times.append(interface.get_event_starting_times_from_ttl(channel_name=channel_name))

        expected_ttl_times = [[1.0 * (1 + period) + 0.1 * channel for period in range(3)] for channel in range(8)]
        self.assertListEqual(list1=inferred_starting_times, list2=expected_ttl_times)

    def test_custom_inferred_ttl_times(self):
        custom_ttl_times = [[1.2], [3.6], [0.7, 4.5], [5.1]]
        interface = MockSpikeGLXNIDQInterface(ttl_times=custom_ttl_times)

        channel_names = ["nidq#XA0", "nidq#XA1", "nidq#XA2", "nidq#XA3"]
        inferred_starting_times = list()
        for channel_index, channel_name in enumerate(channel_names):
            inferred_starting_times.append(interface.get_event_starting_times_from_ttl(channel_name=channel_name))

        self.assertListEqual(list1=inferred_starting_times, list2=custom_ttl_times)

    def test_mock_metadata(self):
        interface = MockSpikeGLXNIDQInterface()

        metadata = interface.get_metadata()

        expected_metadata = dict()
        self.assertDictEqual(d1=metadata, d2=expected_metadata)

    def test_mock_run_conversion(self):
        # TODO
        pass
