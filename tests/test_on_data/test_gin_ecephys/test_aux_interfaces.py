import unittest
from datetime import datetime

import pytest
from parameterized import param, parameterized
from spikeinterface.core.testing import check_recordings_equal
from spikeinterface.extractors import NwbRecordingExtractor

from neuroconv import NWBConverter
from neuroconv.datainterfaces import SpikeGLXNIDQInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH

if not DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    interface_name = param.kwargs["data_interface"].__name__
    reduced_interface_name = interface_name.replace("Interface", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestEcephysAuxNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_aux_list = [
        param(
            data_interface=SpikeGLXNIDQInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_t0.nidq.bin")),
            case_name="load_sync_channel_False",
        ),
        param(
            data_interface=SpikeGLXNIDQInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_t0.nidq.bin"),
                load_sync_channel=True,
            ),
            case_name="load_sync_channel_True",
        ),
    ]

    @parameterized.expand(input=parameterized_aux_list, name_func=custom_name_func)
    def test_aux_recording_extractor_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestAuxRecording=data_interface)

        converter = TestConverter(source_data=dict(TestAuxRecording=interface_kwargs))

        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestAuxRecording"].source_data
                )

        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestAuxRecording"].recording_extractor

        electrical_series_name = metadata["Ecephys"][converter.data_interface_objects["TestAuxRecording"].es_key][
            "name"
        ]

        # NWBRecordingExtractor on spikeinterface does not yet support loading data written from multiple segments.
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

            # Edge case that only occurs in testing; I think it's fixed in > 0.96.1 versions (unreleased as of 1/11/23)
            # The NwbRecordingExtractor on spikeinterface experiences an issue when duplicated channel_ids
            # are specified, which occurs during check_recordings_equal when there is only one channel
            if nwb_recording.get_channel_ids()[0] != nwb_recording.get_channel_ids()[-1]:
                check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=False)
                if recording.has_scaled_traces() and nwb_recording.has_scaled_traces():
                    check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=True)


if __name__ == "__main__":
    unittest.main()
