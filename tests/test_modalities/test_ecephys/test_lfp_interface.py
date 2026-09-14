"""The LFP base forwards the recording base's conversion options; nothing in the repository tested it directly."""

import numpy as np
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces.ecephys.baselfpextractorinterface import BaseLFPExtractorInterface


class MinimalLFPInterface(BaseLFPExtractorInterface):
    """An LFP interface over spikeinterface's generated recording, the way ``MockRecordingInterface`` is built."""

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.core.generate import generate_recording

        return generate_recording

    def _initialize_extractor(self, interface_kwargs: dict):
        # ``generate_recording`` does not take the ``all_annotations`` the recording base adds for real extractors.
        self.extractor_kwargs = {
            key: value for key, value in interface_kwargs.items() if key not in ("verbose", "es_key", "metadata_key")
        }
        return self.get_extractor_class()(**self.extractor_kwargs)


def _make_interface() -> MinimalLFPInterface:
    return MinimalLFPInterface(num_channels=4, sampling_frequency=1_000.0, durations=(1.0,), seed=0)


def test_lfp_interface_writes_to_processing_by_default():
    interface = _make_interface()
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)
    assert "ElectricalSeriesLFP" in nwbfile.processing["ecephys"]["LFP"].electrical_series


def test_lfp_interface_forwards_always_write_timestamps():
    interface = _make_interface()
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, always_write_timestamps=True)
    electrical_series = nwbfile.processing["ecephys"]["LFP"].electrical_series["ElectricalSeriesLFP"]
    np.testing.assert_array_equal(electrical_series.timestamps[:], interface.recording_extractor.get_times())


def test_lfp_interface_forwards_data_representation():
    interface = _make_interface()
    # Heterogeneous offsets are what physical_units is for: a single series cannot carry them as digital counts.
    interface.recording_extractor.set_channel_gains(gains=[0.5, 0.5, 0.5, 0.5])
    interface.recording_extractor.set_channel_offsets(offsets=[0.0, 1.0, 2.0, 3.0])
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, data_representation="physical_units")
    electrical_series = nwbfile.processing["ecephys"]["LFP"].electrical_series["ElectricalSeriesLFP"]
    assert electrical_series.conversion == 1e-6
    assert electrical_series.offset == 0.0
    assert np.issubdtype(np.asarray(electrical_series.data[:5]).dtype, np.floating)


def test_lfp_interface_conversion_options_schema_names_both_options():
    schema = _make_interface().get_conversion_options_schema()
    assert {"always_write_timestamps", "data_representation"} <= set(schema["properties"])
