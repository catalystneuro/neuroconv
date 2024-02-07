from datetime import datetime
from platform import python_version
from sys import platform
from unittest import skip, skipIf

import jsonschema
import numpy as np
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from packaging import version
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    AlphaOmegaRecordingInterface,
    AxonaRecordingInterface,
    BiocamRecordingInterface,
    BlackrockRecordingInterface,
    CellExplorerRecordingInterface,
    EDFRecordingInterface,
    IntanRecordingInterface,
    MaxOneRecordingInterface,
    MCSRawRecordingInterface,
    MEArecRecordingInterface,
    NeuralynxRecordingInterface,
    NeuroScopeRecordingInterface,
    OpenEphysBinaryRecordingInterface,
    OpenEphysLegacyRecordingInterface,
    OpenEphysRecordingInterface,
    PlexonRecordingInterface,
    Spike2RecordingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXRecordingInterface,
    TdtRecordingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


this_python_version = version.parse(python_version())


class TestAlphaOmegaRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = AlphaOmegaRecordingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "alphaomega" / "mpx_map_version4"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 11, 19, 15, 23, 15)


class TestAxonRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = AxonaRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "axona" / "axona_raw.bin"))
    save_directory = OUTPUT_PATH


class TestBiocamRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BiocamRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "biocam" / "biocam_hw3.0_fw1.6.brw"))
    save_directory = OUTPUT_PATH


class TestBlackrockRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BlackrockRecordingInterface
    interface_kwargs = [
        dict(file_path=str(DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns5")),
        dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5")),
        dict(file_path=str(DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns2")),
    ]
    save_directory = OUTPUT_PATH


@skipIf(
    platform == "darwin" or this_python_version < version.parse("3.8") or this_python_version > version.parse("3.9"),
    reason="Interface unsupported for OSX. Only runs on Python 3.8 and 3.9",
)
class TestSpike2RecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Spike2RecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "spike2" / "m365_1sec.smrx"))
    save_directory = OUTPUT_PATH


class TestCellExplorerRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = CellExplorerRecordingInterface
    interface_kwargs = [
        dict(folder_path=str(DATA_PATH / "cellexplorer" / "dataset_4" / "Peter_MS22_180629_110319_concat_stubbed")),
        dict(
            folder_path=str(DATA_PATH / "cellexplorer" / "dataset_4" / "Peter_MS22_180629_110319_concat_stubbed_hdf5")
        ),
    ]
    save_directory = OUTPUT_PATH

    def test_add_channel_metadata_to_nwb(self):
        channel_id = "1"
        expected_channel_properties_recorder = {
            "location": np.array([791.5, -160.0]),
            "brain_area": "CA1 - Field CA1",
            "group": "Group 5",
        }
        expected_channel_properties_electrodes = {
            "rel_x": 791.5,
            "rel_y": -160.0,
            "location": "CA1 - Field CA1",
            "group_name": "Group 5",
        }

        interface_kwargs = self.interface_kwargs
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs
                self.interface = self.data_interface_cls(**self.test_kwargs)
                self.nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{num}_channel.nwb")

                metadata = self.interface.get_metadata()
                metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
                self.interface.run_conversion(
                    nwbfile_path=self.nwbfile_path,
                    overwrite=True,
                    metadata=metadata,
                )

                # Test addition to recording extractor
                recording_extractor = self.interface.recording_extractor
                for key, expected_value in expected_channel_properties_recorder.items():
                    extracted_value = recording_extractor.get_channel_property(channel_id=channel_id, key=key)
                    if key == "location":
                        assert np.allclose(expected_value, extracted_value)
                    else:
                        assert expected_value == extracted_value

                # Test addition to electrodes table
                with NWBHDF5IO(self.nwbfile_path, "r") as io:
                    nwbfile = io.read()
                    electrode_table = nwbfile.electrodes.to_dataframe()
                    electrode_table_row = electrode_table.query(f"channel_name=='{channel_id}'").iloc[0]
                    for key, value in expected_channel_properties_electrodes.items():
                        assert electrode_table_row[key] == value


@skipIf(platform == "darwin", reason="Not supported for OSX.")
class TestEDFRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = EDFRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "edf" / "edf+C.edf"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 3, 2, 10, 42, 19)

    def test_interface_alignment(self):
        interface_kwargs = self.interface_kwargs
        if isinstance(interface_kwargs, dict):
            interface_kwargs = [interface_kwargs]
        for num, kwargs in enumerate(interface_kwargs):
            with self.subTest(str(num)):
                self.case = num
                self.test_kwargs = kwargs

                # TODO - debug hanging I/O from pyedflib
                # self.check_interface_get_original_timestamps()
                # self.check_interface_get_timestamps()
                # self.check_align_starting_time_internal()
                # self.check_align_starting_time_external()
                # self.check_interface_align_timestamps()
                # self.check_shift_timestamps_by_start_time()
                # self.check_interface_original_timestamps_inmutability()

                self.check_nwbfile_temporal_alignment()


class TestIntanRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = IntanRecordingInterface
    interface_kwargs = [
        dict(file_path=str(DATA_PATH / "intan" / "intan_rhd_test_1.rhd")),
        dict(file_path=str(DATA_PATH / "intan" / "intan_rhs_test_1.rhs")),
    ]
    save_directory = OUTPUT_PATH


@skip(reason="This interface fails to load the necessary plugin sometimes.")
class TestMaxOneRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = MaxOneRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert len(metadata["Ecephys"]["Device"]) == 1
        assert metadata["Ecephys"]["Device"][0]["name"] == "DeviceEcephys"
        assert metadata["Ecephys"]["Device"][0]["description"] == "Recorded using Maxwell version '20190530'."


class TestMCSRawRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = MCSRawRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "rawmcs" / "raw_mcs_with_header_1.raw"))
    save_directory = OUTPUT_PATH


class TestMEArecRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = MEArecRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "mearec" / "mearec_test_10s.h5"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert len(metadata["Ecephys"]["Device"]) == 1
        assert metadata["Ecephys"]["Device"][0]["name"] == "Neuronexus-32"
        assert metadata["Ecephys"]["Device"][0]["description"] == "The ecephys device for the MEArec recording."
        # assert len(metadata["Ecephys"]["ElectrodeGroup"]) == 1
        # do not test this condition because in the test we are setting a mock probe
        assert metadata["Ecephys"]["ElectrodeGroup"][0]["device"] == "Neuronexus-32"
        assert metadata["Ecephys"]["ElectricalSeries"]["description"] == (
            '{"angle_tol": 15, "bursting": false, "chunk_duration": 0, "color_noise_floor": 1, '
            '"color_peak": 300, "color_q": 2, "drift_mode": "slow", "drifting": false, '
            '"duration": 10.0, "exp_decay": 0.2, "extract_waveforms": false, '
            '"far_neurons_exc_inh_ratio": 0.8, "far_neurons_max_amp": 10, "far_neurons_n": 300, '
            '"far_neurons_noise_floor": 0.5, "fast_drift_max_jump": 20, "fast_drift_min_jump": 5, '
            '"fast_drift_period": 10, "filter": true, "filter_cutoff": [300, 6000], "filter_order": 3, '
            '"max_burst_duration": 100, "modulation": "electrode", "mrand": 1, '
            '"n_burst_spikes": 10, "n_bursting": null, "n_drifting": null, "n_neurons": 10, '
            '"noise_color": false, "noise_half_distance": 30, "noise_level": 10, '
            '"noise_mode": "uncorrelated", "overlap": false, "preferred_dir": [0, 0, 1], '
            '"sdrand": 0.05, "shape_mod": false, "shape_stretch": 30.0, "slow_drift_velocity": 5, '
            '"sync_jitt": 1, "sync_rate": null, "t_start_drift": 0}'
        )


class TestNeuralynxRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = [
        dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),
        dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data")),
        dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.4.0" / "original_data")),
    ]
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        file_metadata = metadata["NWBFile"]

        if self.case == 0:
            assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 2, 16, 17, 56, 4)
            assert metadata["NWBFile"]["session_id"] == "d8ba8eef-8d11-4cdc-86dc-05f50d4ba13d"
            assert '"FileType": "NCS"' in file_metadata["notes"]
            assert '"recording_closed": "2017-02-16 18:01:18"' in file_metadata["notes"]
            assert '"ADMaxValue": "32767"' in file_metadata["notes"]
            assert '"sampling_rate": "32000.0"' in file_metadata["notes"]
            assert metadata["Ecephys"]["Device"][-1] == {
                "name": "AcqSystem1 DigitalLynxSX",
                "description": "Cheetah 5.7.4",
            }

        elif self.case == 1:
            assert file_metadata["session_start_time"] == datetime(2016, 11, 28, 21, 50, 33, 322000)
            # Metadata extracted directly from file header (neo >= 0.11)
            assert '"FileType": "CSC"' in file_metadata["notes"]
            assert '"recording_closed": "2016-11-28 22:44:41.145000"' in file_metadata["notes"]
            assert '"ADMaxValue": "32767"' in file_metadata["notes"]
            assert '"sampling_rate": "2000.0"' in file_metadata["notes"]
            assert metadata["Ecephys"]["Device"][-1] == {"name": "DigitalLynxSX", "description": "Cheetah 5.6.3"}

        elif self.case == 2:
            assert file_metadata["session_start_time"] == datetime(2001, 1, 1, 0, 0)
            assert '"recording_closed": "2001-01-01 00:00:00"' in file_metadata["notes"]
            assert '"ADMaxValue": "32767"' in file_metadata["notes"]
            assert '"sampling_rate": "1017.375"' in file_metadata["notes"]
            assert metadata["Ecephys"]["Device"][-1] == {"name": "DigitalLynx", "description": "Cheetah 5.4.0"}

    def check_read(self, nwbfile_path):
        super().check_read(nwbfile_path)
        if self.case == 0:
            expected_single_channel_props = {
                "DSPLowCutFilterEnabled": "True",
                "DspLowCutFrequency": "10",
                "DspLowCutNumTaps": "0",
                "DspLowCutFilterType": "DCO",
                "DSPHighCutFilterEnabled": "True",
                "DspHighCutFrequency": "9000",
                "DspHighCutNumTaps": "64",
                "DspHighCutFilterType": "FIR",
                "DspDelayCompensation": "Enabled",
                # don't check for filter delay as the unit might be differently parsed
                # "DspFilterDelay_µs": "984"
            }

            n_channels = self.interface.recording_extractor.get_num_channels()

            for key, exp_value in expected_single_channel_props.items():
                extracted_value = self.interface.recording_extractor.get_property(key)
                # check consistency of number of entries
                assert len(extracted_value) == n_channels
                # check values for first channel
                assert exp_value == extracted_value[0]


class TestMultiStreamNeuralynxRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v6.4.1dev" / "original_data"),
        stream_name="Stream (rate,#packet,t0): (32000.0, 31, 1614363777985169)",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        file_metadata = metadata["NWBFile"]

        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 2, 26, 15, 46, 52)
        assert metadata["NWBFile"]["session_id"] == "f58d55bb-22f6-4682-b3a2-aa116fabb78e"
        assert '"FileType": "NCS"' in file_metadata["notes"]
        assert '"recording_closed": "2021-10-12 09:07:58"' in file_metadata["notes"]
        assert '"ADMaxValue": "32767"' in file_metadata["notes"]
        assert metadata["Ecephys"]["Device"][-1] == {
            "name": "AcqSystem1 DigitalLynxSX",
            "description": "Cheetah 6.4.1.dev0",
        }


class TestNeuroScopeRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuroScopeRecordingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"))
    save_directory = OUTPUT_PATH


class TestOpenEphysBinaryRecordingInterfaceClassMethodsAndAssertions(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = []
    save_directory = OUTPUT_PATH

    def test_get_stream_names(self):
        self.assertCountEqual(
            first=self.data_interface_cls.get_stream_names(
                folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream")
            ),
            second=["Record_Node_107#Neuropix-PXI-116.0", "Record_Node_107#Neuropix-PXI-116.1"],
        )

    def test_folder_structure_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "Unable to identify the OpenEphys folder structure! "
                "Please check that your `folder_path` contains sub-folders of the "
                "following form: 'experiment<index>' -> 'recording<index>' -> 'continuous'."
            ),
        ):
            OpenEphysBinaryRecordingInterface(
                folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream"),
                stream_name="Record_Node_107#Neuropix-PXI-116.0",
            )

    def test_stream_name_missing_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                " `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            ),
        ):
            OpenEphysBinaryRecordingInterface(
                folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107")
            )

    def test_stream_name_not_available_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "The selected stream 'not_a_stream' is not in the available streams "
                "'['Record_Node_107#Neuropix-PXI-116.0', 'Record_Node_107#Neuropix-PXI-116.1']'!"
            ),
        ):
            OpenEphysBinaryRecordingInterface(
                folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
                stream_name="not_a_stream",
            )


class TestOpenEphysBinaryRecordingInterfaceVersion0_4_4(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 2, 15, 17, 20, 4)


class TestOpenEphysBinaryRecordingInterfaceVersion0_5_3_Stream1(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
        stream_name="Record_Node_107#Neuropix-PXI-116.0",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 24, 15, 46, 56)


class TestOpenEphysBinaryRecordingInterfaceVersion0_5_3_Stream2(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
        stream_name="Record_Node_107#Neuropix-PXI-116.1",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 24, 15, 46, 56)


class TestOpenEphysBinaryRecordingInterfaceWithBlocks_version_0_6_block_1_stream_1(
    RecordingExtractorInterfaceTestMixin, TestCase
):
    """From Issue #695, exposed `block_index` argument and added tests on data that include multiple blocks."""

    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_multiexp_multistream" / "Record Node 101"),
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=1,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 5, 3, 10, 52, 24)


class TestOpenEphysLegacyRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysLegacyRecordingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "openephys" / "OpenEphys_SampleData_1"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2018, 10, 3, 13, 16, 50)


class TestOpenEphysRecordingInterfaceRouter(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = OpenEphysRecordingInterface
    interface_kwargs = [
        dict(folder_path=str(DATA_PATH / "openephys" / "OpenEphys_SampleData_1")),
        dict(folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking")),
        dict(
            folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
            stream_name="Record_Node_107#Neuropix-PXI-116.0",
        ),
        dict(
            folder_path=str(DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
            stream_name="Record_Node_107#Neuropix-PXI-116.1",
        ),
    ]
    save_directory = OUTPUT_PATH


class TestSpikeGadgetsRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = SpikeGadgetsRecordingInterface
    interface_kwargs = [
        dict(file_path=str(DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec")),
        dict(file_path=str(DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec"), gains=[0.195]),
        dict(file_path=str(DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec"), gains=[0.385] * 512),
        dict(file_path=str(DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec")),
        dict(file_path=str(DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec"), gains=[0.195]),
        dict(file_path=str(DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec"), gains=[0.385] * 128),
    ]
    save_directory = OUTPUT_PATH


class TestSpikeGLXRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = SpikeGLXRecordingInterface
    interface_kwargs = dict(
        file_path=str(DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.ap.bin")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 3, 10, 35, 10)
        assert metadata["Ecephys"]["Device"][-1] == dict(
            name="Neuropixel-Imec",
            description="{"
            '"probe_type": "0", '
            '"probe_type_description": "NP1.0", '
            '"flex_part_number": "NP2_FLEX_0", '
            '"connected_base_station_part_number": "NP2_QBSC_00"'
            "}",
            manufacturer="Imec",
        )

    def check_electrode_property_helper(self):
        """Check that the helper function returns in the way the NWB GUIDE table component expects."""
        electrode_table_json = self.interface.get_electrode_table_json()

        spikeglx_electrode_table_schema = {
            "type": "array",
            "minItems": 0,
            "items": {"$ref": "#/definitions/SpikeGLXElectrodeColumnEntry"},
            "definitions": {
                "SpikeGLXElectrodeColumnEntry": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "channel_name",
                        "contact_shapes",
                        "gain_to_uV",
                        "offset_to_uV",
                        "group",
                        "group_name",
                        "inter_sample_shift",
                        # "location",
                        "shank_electrode_number",
                    ],
                    "properties": {
                        "channel_name": {"type": "string"},
                        "contact_shapes": {"type": "string"},
                        "gain_to_uV": {"type": "number"},
                        "offset_to_uV": {"type": "number"},
                        "group": {"type": "number"},
                        "group_name": {"type": "string"},
                        "inter_sample_shift": {"type": "number"},
                        "location": {"type": "array"},
                        "shank_electrode_number": {"type": "number"},
                    },
                }
            },
        }
        print(f"{[electrode_table_json[0]]=}")
        jsonschema.validate(instance=[electrode_table_json[0]], schema=spikeglx_electrode_table_schema)

    def run_custom_checks(self):
        self.check_electrode_property_helper()


class TestTdtRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = TdtRecordingInterface
    test_gain_value = 0.195  # arbitrary value to test gain
    interface_kwargs = dict(folder_path=str(DATA_PATH / "tdt" / "aep_05"), gain=test_gain_value)
    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        # Check that the gain is applied
        recording_extractor = self.interface.recording_extractor
        gains = recording_extractor.get_channel_gains()
        expected_channel_gains = [self.test_gain_value] * recording_extractor.get_num_channels()
        assert_array_equal(gains, expected_channel_gains)

    def check_read_nwb(self, nwbfile_path: str):
        from pynwb import NWBHDF5IO

        expected_conversion_factor = self.test_gain_value * 1e-6
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            for _, electrical_series in nwbfile.acquisition.items():
                assert np.isclose(electrical_series.conversion, expected_conversion_factor)

        return super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestPlexonRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = PlexonRecordingInterface
    interface_kwargs = dict(
        # Only File_plexon_3.plx has an ecephys recording stream
        file_path=str(DATA_PATH / "plexon" / "File_plexon_3.plx"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2010, 2, 22, 20, 0, 57)
