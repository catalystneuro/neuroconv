from datetime import datetime
from platform import python_version
from sys import platform

import numpy as np
import pytest
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from packaging import version
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

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
    Plexon2RecordingInterface,
    PlexonLFPInterface,
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
    from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH
except ImportError:
    from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH


this_python_version = version.parse(python_version())


class TestAlphaOmegaRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = AlphaOmegaRecordingInterface
    interface_kwargs = dict(folder_path=str(ECEPHY_DATA_PATH / "alphaomega" / "mpx_map_version4"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 11, 19, 15, 23, 15)


class TestAxonRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = AxonaRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "axona" / "axona_raw.bin"))
    save_directory = OUTPUT_PATH


class TestBiocamRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = BiocamRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "biocam" / "biocam_hw3.0_fw1.6.brw"))
    save_directory = OUTPUT_PATH


class TestBlackrockRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = BlackrockRecordingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(file_path=str(ECEPHY_DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns5")),
            dict(file_path=str(ECEPHY_DATA_PATH / "blackrock" / "FileSpec2.3001.ns5")),
            dict(file_path=str(ECEPHY_DATA_PATH / "blackrock" / "blackrock_2_1" / "l101210-001.ns2")),
        ],
        ids=["multi_stream_case_ns5", "blackrock_ns5_v2", "multi_stream_case_ns2"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


@pytest.mark.skipif(
    platform == "darwin" or this_python_version > version.parse("3.9"),
    reason="Interface unsupported for OSX. Interface only runs on Python 3.9",
)
class TestSpike2RecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = Spike2RecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "spike2" / "m365_1sec.smrx"))
    save_directory = OUTPUT_PATH


class TestCellExplorerRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = CellExplorerRecordingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(
                folder_path=str(
                    ECEPHY_DATA_PATH / "cellexplorer" / "dataset_4" / "Peter_MS22_180629_110319_concat_stubbed"
                )
            ),
            dict(
                folder_path=str(
                    ECEPHY_DATA_PATH / "cellexplorer" / "dataset_4" / "Peter_MS22_180629_110319_concat_stubbed_hdf5"
                )
            ),
        ],
        ids=["matlab", "hdf5"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_add_channel_metadata_to_nwb(self, setup_interface):
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

        self.nwbfile_path = str(
            self.save_directory / f"{self.data_interface_cls.__name__}_{self.test_name}_channel.nwb"
        )

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

        # Test addition to electrodes table!~
        with NWBHDF5IO(self.nwbfile_path, "r") as io:
            nwbfile = io.read()
            electrode_table = nwbfile.electrodes.to_dataframe()
            electrode_table_row = electrode_table.query(f"channel_name=='{channel_id}'").iloc[0]
            for key, value in expected_channel_properties_electrodes.items():
                assert electrode_table_row[key] == value


@pytest.mark.skipif(
    platform == "darwin",
    reason="Interface unsupported for OSX.",
)
class TestEDFRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = EDFRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "edf" / "edf+C.edf"))
    save_directory = OUTPUT_PATH

    def check_run_conversion_with_backend(self, nwbfile_path: str, backend="hdf5"):
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            backend=backend,
            **self.conversion_options,
        )

    def test_all_conversion_checks(self, setup_interface, tmp_path):
        # Create a unique test name and file path
        nwbfile_path = str(tmp_path / f"{self.__class__.__name__}.nwb")
        self.nwbfile_path = nwbfile_path

        # Now run the checks using the setup objects
        metadata = self.interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 3, 2, 10, 42, 19)

        self.check_run_conversion_with_backend(nwbfile_path=nwbfile_path, backend="hdf5")
        self.check_read_nwb(nwbfile_path=nwbfile_path)

    # EDF has simultaneous access issues; can't have multiple interfaces open on the same file at once...
    def test_metadata_schema_valid(self):
        pass

    def test_no_metadata_mutation(self):
        pass

    def test_run_conversion_with_backend(self):
        pass

    def test_run_conversion_with_backend_configuration(self):
        pass

    def test_interface_alignment(self):
        pass

    def test_configure_backend_for_equivalent_nwbfiles(self):
        pass

    def test_conversion_options_schema_valid(self):
        pass

    def test_metadata(self):
        pass

    def test_conversion_options_schema_valid(self):
        pass


class TestIntanRecordingInterfaceRHS(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = IntanRecordingInterface
    interface_kwargs = dict(file_path=ECEPHY_DATA_PATH / "intan" / "intan_rhs_test_1.rhs")


class TestIntanRecordingInterfaceRHD(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = IntanRecordingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(file_path=ECEPHY_DATA_PATH / "intan" / "intan_rhd_test_1.rhd"),
            dict(file_path=ECEPHY_DATA_PATH / "intan" / "intan_fpc_test_231117_052630/info.rhd"),
            dict(file_path=ECEPHY_DATA_PATH / "intan" / "intan_fps_test_231117_052500/info.rhd"),
        ],
        ids=["rhd", "one-file-per-channel", "one-file-per-signal"],
    )
    def setup_interface(self, request):

        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_devices_written_correctly(self, setup_interface):

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile)

        nwbfile.devices["Intan"].name == "Intan"
        len(nwbfile.devices) == 1

        nwbfile.devices["Intan"].description == "RHD Recording System"

    def test_not_adding_extra_devices_when_recording_has_groups(self, setup_interface):
        # Test that no extra-devices are added when the recording has groups

        nwbfile = mock_NWBFile()
        recording = self.interface.recording_extractor
        num_channels = recording.get_num_channels()
        channel_groups = np.full(shape=num_channels, fill_value=0, dtype=int)
        channel_groups[::2] = 1  # Every other channel is in group 1, the rest are in group 0
        recording.set_channel_groups(groups=channel_groups)

        self.interface.add_to_nwbfile(nwbfile=nwbfile)
        assert len(nwbfile.devices) == 1

        nwbfile = mock_NWBFile()
        recording = self.interface.recording_extractor
        num_channels = recording.get_num_channels()
        group_names = np.full(shape=num_channels, fill_value="A", dtype="str")
        group_names[::2] = "B"  # Every other channel group is named B, the rest are named A
        recording.set_property("group_name", group_names)

        self.interface.add_to_nwbfile(nwbfile=nwbfile)
        assert len(nwbfile.devices) == 1


@pytest.mark.skip(reason="This interface fails to load the necessary plugin sometimes.")
class TestMaxOneRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MaxOneRecordingInterface
    interface_kwargs = dict(
        file_path=str(ECEPHY_DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert len(metadata["Ecephys"]["Device"]) == 1
        assert metadata["Ecephys"]["Device"][0]["name"] == "DeviceEcephys"
        assert metadata["Ecephys"]["Device"][0]["description"] == "Recorded using Maxwell version '20190530'."


class TestMCSRawRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MCSRawRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "rawmcs" / "raw_mcs_with_header_1.raw"))
    save_directory = OUTPUT_PATH


class TestMEArecRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MEArecRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "mearec" / "mearec_test_10s.h5"))
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


class TestNeuralynxRecordingInterfaceV574:
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = (dict(folder_path=str(ECEPHY_DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data")),)

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        file_metadata = metadata["NWBFile"]
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

    def check_read(self, nwbfile_path):
        super().check_read(nwbfile_path)
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
        }

        n_channels = self.interface.recording_extractor.get_num_channels()

        for key, exp_value in expected_single_channel_props.items():
            extracted_value = self.interface.recording_extractor.get_property(key)
            assert len(extracted_value) == n_channels
            assert exp_value == extracted_value[0]


class TestNeuralynxRecordingInterfaceV563:
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = (dict(folder_path=str(ECEPHY_DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data")),)

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        file_metadata = metadata["NWBFile"]
        assert file_metadata["session_start_time"] == datetime(2016, 11, 28, 21, 50, 33, 322000)
        assert '"FileType": "CSC"' in file_metadata["notes"]
        assert '"recording_closed": "2016-11-28 22:44:41.145000"' in file_metadata["notes"]
        assert '"ADMaxValue": "32767"' in file_metadata["notes"]
        assert '"sampling_rate": "2000.0"' in file_metadata["notes"]
        assert metadata["Ecephys"]["Device"][-1] == {"name": "DigitalLynxSX", "description": "Cheetah 5.6.3"}

    def check_read(self, nwbfile_path):
        super().check_read(nwbfile_path)
        # Add any specific checks for Cheetah_v5.6.3 if needed


class TestNeuralynxRecordingInterfaceV540:
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = (dict(folder_path=str(ECEPHY_DATA_PATH / "neuralynx" / "Cheetah_v5.4.0" / "original_data")),)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        file_metadata = metadata["NWBFile"]
        assert file_metadata["session_start_time"] == datetime(2001, 1, 1, 0, 0)
        assert '"recording_closed": "2001-01-01 00:00:00"' in file_metadata["notes"]
        assert '"ADMaxValue": "32767"' in file_metadata["notes"]
        assert '"sampling_rate": "1017.375"' in file_metadata["notes"]
        assert metadata["Ecephys"]["Device"][-1] == {"name": "DigitalLynx", "description": "Cheetah 5.4.0"}

    def check_read(self, nwbfile_path):
        super().check_read(nwbfile_path)
        # Add any specific checks for Cheetah_v5.4.0 if need


class TestMultiStreamNeuralynxRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = NeuralynxRecordingInterface
    interface_kwargs = dict(
        folder_path=str(ECEPHY_DATA_PATH / "neuralynx" / "Cheetah_v6.4.1dev" / "original_data"),
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


class TestNeuroScopeRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = NeuroScopeRecordingInterface
    interface_kwargs = dict(file_path=str(ECEPHY_DATA_PATH / "neuroscope" / "test1" / "test1.dat"))
    save_directory = OUTPUT_PATH


class TestOpenEphysBinaryRecordingInterfaceClassMethodsAndAssertions:

    data_interface_cls = OpenEphysBinaryRecordingInterface

    def test_get_stream_names(self):

        stream_names = self.data_interface_cls.get_stream_names(
            folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107")
        )

        assert stream_names == ["Record_Node_107#Neuropix-PXI-116.0", "Record_Node_107#Neuropix-PXI-116.1"]

    def test_folder_structure_assertion(self):
        with pytest.raises(
            ValueError,
            match=r"Unable to identify the OpenEphys folder structure! Please check that your `folder_path` contains a settings.xml file and sub-folders of the following form: 'experiment<index>' -> 'recording<index>' -> 'continuous'.",
        ):
            OpenEphysBinaryRecordingInterface(folder_path=str(ECEPHY_DATA_PATH / "openephysbinary"))

    def test_stream_name_missing_assertion(self):
        with pytest.raises(
            ValueError,
            match=r"More than one stream is detected! Please specify which stream you wish to load with the `stream_name` argument. To see what streams are available, call\s+`OpenEphysRecordingInterface.get_stream_names\(folder_path=\.\.\.\)`.",
        ):
            OpenEphysBinaryRecordingInterface(
                folder_path=str(
                    ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"
                )
            )

    def test_stream_name_not_available_assertion(self):
        with pytest.raises(
            ValueError,
            match=r"The selected stream 'not_a_stream' is not in the available streams '\['Record_Node_107#Neuropix-PXI-116.0', 'Record_Node_107#Neuropix-PXI-116.1'\]'!",
        ):
            OpenEphysBinaryRecordingInterface(
                folder_path=str(
                    ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"
                ),
                stream_name="not_a_stream",
            )


class TestOpenEphysBinaryRecordingInterfaceVersion0_4_4(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 2, 15, 17, 20, 4)


class TestOpenEphysBinaryRecordingInterfaceVersion0_5_3_Stream1(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
        stream_name="Record_Node_107#Neuropix-PXI-116.0",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 24, 15, 46, 56)


class TestOpenEphysBinaryRecordingInterfaceVersion0_5_3_Stream2(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"),
        stream_name="Record_Node_107#Neuropix-PXI-116.1",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 24, 15, 46, 56)


class TestOpenEphysBinaryRecordingInterfaceWithBlocks_version_0_6_block_1_stream_1(
    RecordingExtractorInterfaceTestMixin
):
    """From Issue #695, exposed `block_index` argument and added tests on data that include multiple blocks."""

    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(
            ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_multiexp_multistream" / "Record Node 101"
        ),
        stream_name="Record Node 101#NI-DAQmx-103.PXIe-6341",
        block_index=1,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 5, 3, 10, 52, 24)


class TestOpenEphysBinaryRecordingInterfaceNonNeuralDatExcluded(RecordingExtractorInterfaceTestMixin):
    """Test that non-neural channels are not written as ElectricalSeries"""

    data_interface_cls = OpenEphysBinaryRecordingInterface
    interface_kwargs = dict(
        folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "neural_and_non_neural_data_mixed"),
        stream_name="Rhythm_FPGA-100.0",
    )
    save_directory = OUTPUT_PATH

    def test_non_neural_channels_not_added(self, setup_interface):
        interface, test_name = setup_interface
        nwbfile = interface.create_nwbfile()

        written_channels = nwbfile.acquisition["ElectricalSeries"].electrodes["channel_name"].data
        # Note the absence of "ADC1" and "ADC2"
        assert all("ADC" not in channel for channel in written_channels)
        assert np.array_equal(written_channels, np.asarray(["CH1", "CH2", "CH3", "CH4"]))


class TestOpenEphysLegacyRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = OpenEphysLegacyRecordingInterface
    interface_kwargs = dict(folder_path=str(ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2018, 10, 3, 13, 16, 50)


class TestOpenEphysRecordingInterfaceRouter(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = OpenEphysRecordingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(folder_path=str(ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1")),
            dict(folder_path=str(ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking")),
            dict(
                folder_path=str(
                    ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"
                ),
                stream_name="Record_Node_107#Neuropix-PXI-116.0",
            ),
            dict(
                folder_path=str(
                    ECEPHY_DATA_PATH / "openephysbinary" / "v0.5.3_two_neuropixels_stream" / "Record_Node_107"
                ),
                stream_name="Record_Node_107#Neuropix-PXI-116.1",
            ),
        ],
        ids=[
            "OpenEphys_SampleData_1",
            "v0.4.4.1_with_video_tracking",
            "Record_Node_107_Neuropix-PXI-116.0",
            "Record_Node_107_Neuropix-PXI-116.1",
        ],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_interface_extracted_metadata(self, setup_interface):
        interface, test_name = setup_interface
        metadata = interface.get_metadata()
        assert "NWBFile" in metadata  # Example assertion
        # Additional assertions specific to the metadata can be added here


class TestOpenEphysRecordingInterfaceRedirects(TestCase):
    def test_legacy_format(self):
        folder_path = ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"

        interface = OpenEphysRecordingInterface(folder_path=folder_path)
        self.assertIsInstance(interface, OpenEphysLegacyRecordingInterface)

    def test_propagate_stream_name(self):
        folder_path = ECEPHY_DATA_PATH / "openephys" / "OpenEphys_SampleData_1"
        exc_msg = "The selected stream 'AUX' is not in the available streams '['Signals CH']'!"
        with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path, stream_name="AUX")

    def test_binary_format(self):
        folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"
        interface = OpenEphysRecordingInterface(folder_path=folder_path)
        self.assertIsInstance(interface, OpenEphysBinaryRecordingInterface)

    def test_unrecognized_format(self):
        folder_path = ECEPHY_DATA_PATH / "plexon"
        exc_msg = "The Open Ephys data must be in 'legacy' (.continuous) or in 'binary' (.dat) format."
        with self.assertRaisesWith(AssertionError, exc_msg=exc_msg):
            OpenEphysRecordingInterface(folder_path=folder_path)


class TestSpikeGadgetsRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = SpikeGadgetsRecordingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec")),
            dict(file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec"), gains=[0.195]),
            dict(
                file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "20210225_em8_minirec2_ac.rec"), gains=[0.385] * 512
            ),
            dict(file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec")),
            dict(file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec"), gains=[0.195]),
            dict(
                file_path=str(ECEPHY_DATA_PATH / "spikegadgets" / "W122_06_09_2019_1_fromSD.rec"), gains=[0.385] * 128
            ),
        ],
        ids=[
            "20210225_em8_minirec2_ac_default_gains",
            "20210225_em8_minirec2_ac_gains_0.195",
            "20210225_em8_minirec2_ac_gains_0.385x512",
            "W122_06_09_2019_1_fromSD_default_gains",
            "W122_06_09_2019_1_fromSD_gains_0.195",
            "W122_06_09_2019_1_fromSD_gains_0.385x128",
        ],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_extracted_metadata(self, setup_interface):
        interface, test_name = setup_interface
        metadata = interface.get_metadata()
        # Example assertion
        assert "NWBFile" in metadata
        # Additional assertions specific to the metadata can be added here


class TestSpikeGLXRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = SpikeGLXRecordingInterface
    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0", stream_id="imec0.ap"
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 11, 3, 10, 35, 10)
        assert metadata["Ecephys"]["Device"][-1] == dict(
            name="NeuropixelsImec0",
            description="{"
            '"probe_type": "0", '
            '"probe_type_description": "NP1.0", '
            '"flex_part_number": "NP2_FLEX_0", '
            '"connected_base_station_part_number": "NP2_QBSC_00"'
            "}",
            manufacturer="Imec",
        )


class TestSpikeGLXRecordingInterfaceLongNHP(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = SpikeGLXRecordingInterface
    interface_kwargs = dict(
        file_path=str(
            ECEPHY_DATA_PATH
            / "spikeglx"
            / "long_nhp_stubbed"
            / "snippet_g0"
            / "snippet_g0_imec0"
            / "snippet_g0_t0.imec0.ap.bin"
        )
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2024, 1, 3, 11, 51, 51)
        assert metadata["Ecephys"]["Device"][-1] == dict(
            name="NeuropixelsImec0",
            description="{"
            '"probe_type": "1030", '
            '"probe_type_description": "NP1.0 NHP", '
            '"flex_part_number": "NPNH_AFLEX_00", '
            '"connected_base_station_part_number": "NP2_QBSC_00"'
            "}",
            manufacturer="Imec",
        )


class TestTdtRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = TdtRecordingInterface
    test_gain_value = 0.195  # arbitrary value to test gain
    interface_kwargs = dict(folder_path=str(ECEPHY_DATA_PATH / "tdt" / "aep_05"), gain=test_gain_value)
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


class TestPlexonRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = PlexonRecordingInterface
    interface_kwargs = dict(
        file_path=str(ECEPHY_DATA_PATH / "plexon" / "4chDemoPLX.plx"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2013, 11, 19, 13, 48, 13)


class TestPlexonLFPInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = PlexonLFPInterface
    interface_kwargs = dict(
        file_path=str(ECEPHY_DATA_PATH / "plexon" / "4chDemoPLX.plx"),
    )
    save_directory = OUTPUT_PATH
    is_lfp_interface = True


def is_macos():
    import platform

    return platform.system() == "Darwin"


@pytest.mark.skipif(
    is_macos(),
    reason="Test skipped on macOS.",
)
class TestPlexon2RecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = Plexon2RecordingInterface
    interface_kwargs = dict(
        file_path=str(ECEPHY_DATA_PATH / "plexon" / "4chDemoPL2.pl2"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2013, 11, 20, 15, 59, 39)
