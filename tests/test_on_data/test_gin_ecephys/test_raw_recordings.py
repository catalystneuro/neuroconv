import unittest
import pytest
import itertools
from datetime import datetime
from platform import python_version
from sys import platform

from packaging import version
from parameterized import parameterized, param
from spikeinterface.core.testing import check_recordings_equal
from spikeinterface.extractors import NwbRecordingExtractor
from spikeinterface.core import BaseRecording

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    CEDRecordingInterface,
    IntanRecordingInterface,
    NeuralynxRecordingInterface,
    NeuroScopeRecordingInterface,
    OpenEphysRecordingInterface,
    OpenEphysBinaryRecordingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXRecordingInterface,
    BlackrockRecordingInterface,
    AxonaRecordingInterface,
    EDFRecordingInterface,
    TdtRecordingInterface,
    PlexonRecordingInterface,
    BiocamRecordingInterface,
    AlphaOmegaRecordingInterface,
    MEArecRecordingInterface,
    MCSRawRecordingInterface,
    MaxOneRecordingInterface,
)

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
    reduced_interface_name = interface_name.replace("Recording", "").replace("Interface", "").replace("Sorting", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestEcephysRawRecordingsNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_recording_list = [
        param(
            data_interface=AxonaRecordingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "axona" / "axona_raw.bin")),
        ),
        param(
            data_interface=EDFRecordingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "edf" / "edf+C.edf")),
            case_name="artificial_data",
        ),
        param(
            data_interface=TdtRecordingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "tdt" / "aep_05")),
            case_name="multi_segment",
        ),
        param(
            data_interface=BlackrockRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns5"),
            ),
            case_name="multi_stream_case_ns5",
        ),
        param(
            data_interface=BlackrockRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns2"),
            ),
            case_name="multi_stream_case_ns2",
        ),
        param(
            data_interface=PlexonRecordingInterface,
            interface_kwargs=dict(
                # Only File_plexon_3.plx has an ecephys recording stream
                file_path=str(DATA_PATH / "plexon" / "File_plexon_3.plx"),
            ),
            case_name="plexon_recording",
        ),
        param(
            data_interface=BiocamRecordingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "biocam" / "biocam_hw3.0_fw1.6.brw")),
            case_name="biocam",
        ),
        param(
            data_interface=AlphaOmegaRecordingInterface,
            interface_kwargs=dict(
                folder_path=str(DATA_PATH / "alphaomega" / "mpx_map_version4"),
            ),
            case_name="alphaomega",
        ),
        param(
            data_interface=MEArecRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "mearec" / "mearec_test_10s.h5"),
            ),
            case_name="mearec",
        ),
        param(
            data_interface=MCSRawRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "rawmcs" / "raw_mcs_with_header_1.raw"),
            ),
            case_name="rawmcs",
        ),
        param(
            data_interface=SpikeGLXRecordingInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.ap.bin"
                ),
            ),
        ),
        param(
            data_interface=NeuralynxRecordingInterface,
            interface_kwargs=dict(
                folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data"),
            ),
            case_name="neuralynx",
        ),
        param(
            data_interface=OpenEphysBinaryRecordingInterface,
            interface_kwargs=dict(
                folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"),
            ),
        ),
        param(
            data_interface=BlackrockRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5"),
            ),
        ),
        param(
            data_interface=NeuroScopeRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"),
            ),
        ),
    ]
    this_python_version = version.parse(python_version())
    if platform != "darwin" and version.parse("3.8") <= this_python_version < version.parse("3.10"):
        parameterized_recording_list.append(
            param(
                data_interface=CEDRecordingInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / "spike2" / "m365_1sec.smrx")),
                case_name="smrx",
            )
        )

    for suffix in ["rhd", "rhs"]:
        parameterized_recording_list.append(
            param(
                data_interface=IntanRecordingInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / "intan" / f"intan_{suffix}_test_1.{suffix}"),
                ),
                case_name=suffix,
            )
        )

    file_name_list = ["20210225_em8_minirec2_ac", "W122_06_09_2019_1_fromSD"]
    num_channels_list = [512, 128]
    file_name_num_channels_pairs = zip(file_name_list, num_channels_list)
    gains_list = [None, [0.195], [0.385]]
    for iteration in itertools.product(file_name_num_channels_pairs, gains_list):
        (file_name, num_channels), gains = iteration

        interface_kwargs = dict(
            file_path=str(DATA_PATH / "spikegadgets" / f"{file_name}.rec"),
        )

        if gains is not None:
            if gains[0] == 0.385:
                gains = gains * num_channels
            interface_kwargs.update(gains=gains)
            gain_string = gains[0]
        else:
            gain_string = None

        case_name = f"{file_name}, num_channels={num_channels}, gains={gain_string}, "
        parameterized_recording_list.append(
            param(data_interface=SpikeGadgetsRecordingInterface, interface_kwargs=interface_kwargs, case_name=case_name)
        )

    @classmethod
    def setUpClass(cls):
        hdf5_plugin_path = str(HDF5_PLUGIN_PATH)
        MaxOneRecordingInterface.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)
        os.environ["HDF5_PLUGIN_PATH"] = hdf5_plugin_path

    @parameterized.expand(input=parameterized_recording_list, name_func=custom_name_func)
    def test_recording_extractor_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=data_interface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestRecording"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestRecording"].recording_extractor

        es_key = converter.get_conversion_options()["TestRecording"].get("es_key", None)
        electrical_series_name = metadata["Ecephys"][es_key]["name"] if es_key else None
        if not isinstance(recording, BaseRecording):
            raise ValueError("recordings of interfaces should be BaseRecording objects from spikeinterface ")

        # NWBRecordingExtractor on spikeinterface does not yet support loading data written from multiple segment.
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

            # Edge case that only occurs in testing, but should eventually be fixed nonetheless
            # The NwbRecordingExtractor on spikeinterface experiences an issue when duplicated channel_ids
            # are specified, which occurs during check_recordings_equal when there is only one channel
            if nwb_recording.get_channel_ids()[0] != nwb_recording.get_channel_ids()[-1]:
                check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=False)
                if recording.has_scaled_traces() and nwb_recording.has_scaled_traces():
                    check_recordings_equal(RX1=recording, RX2=nwb_recording, return_scaled=True)


if __name__ == "__main__":
    unittest.main()
,