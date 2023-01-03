import os
import unittest
import itertools
from pathlib import Path
from datetime import datetime
from platform import python_version
from sys import platform

import numpy as np
import numpy.testing as npt
from pynwb import NWBHDF5IO
from packaging import version
from parameterized import parameterized, param
from spikeextractors import NwbSortingExtractor, SortingExtractor
from spikeextractors.testing import check_sortings_equal
from spikeinterface.core.testing import check_recordings_equal
from spikeinterface.core.testing import check_sortings_equal as check_sorting_equal_si
from spikeinterface.extractors import NwbRecordingExtractor
from spikeinterface.extractors import NwbSortingExtractor as NwbSortingExtractorSI
from spikeinterface.core import BaseRecording


from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    CellExplorerSortingInterface,
    CEDRecordingInterface,
    IntanRecordingInterface,
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
    NeuroScopeRecordingInterface,
    NeuroScopeLFPInterface,
    NeuroScopeSortingInterface,
    OpenEphysRecordingInterface,
    PhySortingInterface,
    KiloSortSortingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXLFPInterface,
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
    AxonaRecordingInterface,
    AxonaLFPDataInterface,
    EDFRecordingInterface,
    TdtRecordingInterface,
    PlexonRecordingInterface,
    BiocamRecordingInterface,
    AlphaOmegaRecordingInterface,
    MEArecRecordingInterface,
    MCSRawRecordingInterface,
    MaxOneRecordingInterface,
    MaxTwoRecordingInterface,
)


from .setup_paths import ECEPHY_DATA_PATH as DATA_PATH
from .setup_paths import OUTPUT_PATH, HDF5_PLUGIN_PATH


def custom_name_func(testcase_func, param_num, param):
    interface_name = param.kwargs["data_interface"].__name__
    reduced_interface_name = interface_name.replace("Recording", "").replace("Interface", "").replace("Sorting", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestEcephysNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_lfp_list = [
        param(
            data_interface=AxonaLFPDataInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "axona" / "dataset_unit_spikes" / "20140815-180secs.eeg")),
        ),
        param(
            data_interface=NeuroScopeLFPInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.eeg"),
                xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
            ),
        ),
    ]

    @classmethod
    def setUpClass(cls):
        hdf5_plugin_path = str(HDF5_PLUGIN_PATH)
        MaxOneRecordingInterface.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)
        os.environ["HDF5_PLUGIN_PATH"] = hdf5_plugin_path

    @parameterized.expand(input=parameterized_lfp_list, name_func=custom_name_func)
    def test_convert_lfp_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestLFP=data_interface)

        converter = TestConverter(source_data=dict(TestLFP=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(member=interface_kwarg, container=converter.data_interface_objects["TestLFP"].source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestLFP"].recording_extractor
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            nwb_lfp_electrical_series = nwbfile.processing["ecephys"]["LFP"]["ElectricalSeriesLFP"]
            nwb_lfp_unscaled = nwb_lfp_electrical_series.data[:]
            nwb_lfp_conversion = nwb_lfp_electrical_series.conversion
            if not isinstance(recording, BaseRecording):
                raise ValueError("recordings of interfaces should be BaseRecording objects from spikeinterface ")

            npt.assert_array_equal(x=recording.get_traces(return_scaled=False), y=nwb_lfp_unscaled)
            # This can only be tested if both gain and offest are present
            if recording.has_scaled_traces():
                channel_conversion = nwb_lfp_electrical_series.channel_conversion
                nwb_lfp_conversion_vector = (
                    channel_conversion[:]
                    if channel_conversion is not None
                    else np.ones(shape=nwb_lfp_unscaled.shape[1])
                )

                nwb_lfp_offset = nwb_lfp_electrical_series.offset
                recording_data_volts = recording.get_traces(return_scaled=True) * 1e-6
                nwb_data_volts = nwb_lfp_unscaled * nwb_lfp_conversion_vector * nwb_lfp_conversion + nwb_lfp_offset
                npt.assert_array_almost_equal(x=recording_data_volts, y=nwb_data_volts)

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
            data_interface=MaxOneRecordingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "maxwell" / "MaxOne_data" / "Record" / "000011" / "data.raw.h5"),
            ),
            case_name="maxone",
        ),
    ]
    this_python_version = version.parse(python_version())
    if (
        platform != "darwin"
        and this_python_version >= version.parse("3.8")
        and this_python_version < version.parse("3.10")
    ):
        parameterized_recording_list.append(
            param(
                data_interface=CEDRecordingInterface,
                interface_kwargs=dict(file_path=str(DATA_PATH / "spike2" / "m365_1sec.smrx")),
                case_name="smrx",
            )
        )
    parameterized_recording_list.append(
        param(
            data_interface=NeuralynxRecordingInterface,
            interface_kwargs=dict(
                folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.7.4" / "original_data"),
            ),
            case_name="neuralynx",
        )
    )

    for spikeextractors_backend in [True, False]:
        parameterized_recording_list.append(
            param(
                data_interface=OpenEphysRecordingInterface,
                interface_kwargs=dict(
                    folder_path=str(DATA_PATH / "openephysbinary" / "v0.4.4.1_with_video_tracking"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    for spikeextractors_backend in [True, False]:
        parameterized_recording_list.append(
            param(
                data_interface=BlackrockRecordingInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    for suffix, spikeextractors_backend in itertools.product(["rhd", "rhs"], [True, False]):
        parameterized_recording_list.append(
            param(
                data_interface=IntanRecordingInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / "intan" / f"intan_{suffix}_test_1.{suffix}"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"{suffix}, spikeextractors_backend={spikeextractors_backend}",
            )
        )

    file_name_list = ["20210225_em8_minirec2_ac", "W122_06_09_2019_1_fromSD"]
    num_channels_list = [512, 128]
    file_name_num_channels_pairs = zip(file_name_list, num_channels_list)
    gains_list = [None, [0.195], [0.385]]
    for iteration in itertools.product(file_name_num_channels_pairs, gains_list, [True, False]):
        (file_name, num_channels), gains, spikeextractors_backend = iteration

        interface_kwargs = dict(
            file_path=str(DATA_PATH / "spikegadgets" / f"{file_name}.rec"),
            spikeextractors_backend=spikeextractors_backend,
        )

        if gains is not None:
            if gains[0] == 0.385:
                gains = gains * num_channels
            interface_kwargs.update(gains=gains)
            gain_string = gains[0]
        else:
            gain_string = None

        case_name = (
            f"{file_name}, num_channels={num_channels}, gains={gain_string}, "
            f"spikeextractors_backend={spikeextractors_backend}"
        )
        parameterized_recording_list.append(
            param(data_interface=SpikeGadgetsRecordingInterface, interface_kwargs=interface_kwargs, case_name=case_name)
        )

    for spikeextractors_backend in [False]:  # Cannot run since legacy spikeextractors cannot read new GIN file
        sub_path = Path("spikeglx") / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
        parameterized_recording_list.append(
            param(
                data_interface=SpikeGLXRecordingInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / sub_path / "Noise4Sam_g0_t0.imec0.ap.bin"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    for spikeextractors_backend in [True, False]:
        sub_path = Path("spikeglx") / "Noise4Sam_g0" / "Noise4Sam_g0_imec0"
        parameterized_recording_list.append(
            param(
                data_interface=SpikeGLXLFPInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / sub_path / "Noise4Sam_g0_t0.imec0.lf.bin"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    for spikeextractors_backend in [True, False]:
        parameterized_recording_list.append(
            param(
                data_interface=NeuroScopeRecordingInterface,
                interface_kwargs=dict(
                    file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    for recording_name in ["rec0000", "rec0001"]:
        for stream_name in ["well000", "well001", "well002", "well003", "well004", "well005"]:
            parameterized_recording_list.append(
                param(
                    data_interface=MaxTwoRecordingInterface,
                    interface_kwargs=dict(
                        file_path=str(
                            DATA_PATH / "maxwell" / "MaxTwo_data" / "Activity_Scan" / "000021" / "data.raw.h5"
                        ),
                        recording_name=recording_name,
                        stream_name=stream_name,
                    ),
                    case_name=f"maxtwo-recording_name={recording_name}-stream_name={stream_name}",
                ),
            )

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

    parameterized_sorting_list = [
        param(
            data_interface=KiloSortSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0")),
        ),
        param(
            data_interface=BlackrockSortingInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev")),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_1" / "20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
                )
            ),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "cellexplorer" / "dataset_2" / "20170504_396um_0um_merge.spikes.cellinfo.mat")
            ),
        ),
        param(
            data_interface=CellExplorerSortingInterface,
            interface_kwargs=dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_3" / "20170519_864um_900um_merge.spikes.cellinfo.mat"
                )
            ),
        ),
        param(
            data_interface=NeuralynxSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.5.1" / "original_data")),
            case_name="mono_electrodes",
        ),
        param(
            data_interface=NeuralynxSortingInterface,
            interface_kwargs=dict(folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data")),
            case_name="tetrodes",
        ),
    ]

    for spikeextractors_backend in [False, True]:
        parameterized_sorting_list.append(
            param(
                data_interface=NeuroScopeSortingInterface,
                interface_kwargs=dict(
                    folder_path=str(DATA_PATH / "neuroscope" / "dataset_1"),
                    xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

        parameterized_sorting_list.append(
            param(
                data_interface=PhySortingInterface,
                interface_kwargs=dict(
                    folder_path=str(DATA_PATH / "phy" / "phy_example_0"),
                    spikeextractors_backend=spikeextractors_backend,
                ),
                case_name=f"spikeextractors_backend={spikeextractors_backend}",
            )
        )

    @parameterized.expand(input=parameterized_sorting_list, name_func=custom_name_func)
    def test_convert_sorting_extractor_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestSorting=data_interface)

        converter = TestConverter(source_data=dict(TestSorting=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestSorting"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        sorting = converter.data_interface_objects["TestSorting"].sorting_extractor
        sf = sorting.get_sampling_frequency()
        if sf is None:  # need to set dummy sampling frequency since no associated acquisition in file
            sf = 30000
            sorting.set_sampling_frequency(sf)

        if isinstance(sorting, SortingExtractor):
            nwb_sorting = NwbSortingExtractor(file_path=nwbfile_path, sampling_frequency=sf)
            check_sortings_equal(SX1=sorting, SX2=nwb_sorting)
        else:
            # NWBSortingExtractor on spikeinterface does not yet support loading data written from multiple segment.
            if sorting.get_num_segments() == 1:
                nwb_sorting = NwbSortingExtractorSI(file_path=nwbfile_path, sampling_frequency=sf)
                check_sorting_equal_si(SX1=sorting, SX2=nwb_sorting)

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_gains(self, name, conversion_options):
        input_gain = 2.0
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=input_gain)

        nwbfile_path = str(self.savedir / f"test_neuroscope_gains_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            # output_channel_conversion = nwbfile.acquisition["ElectricalSeriesRaw"].channel_conversion[:]
            # input_gain_array = np.ones_like(output_channel_conversion) * input_gain
            # np.testing.assert_array_almost_equal(input_gain_array, output_channel_conversion)
            assert nwbfile.acquisition["ElectricalSeriesRaw"].channel_conversion is None

            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            nwb_recording_gains = nwb_recording.get_channel_gains()
            npt.assert_almost_equal(input_gain * np.ones_like(nwb_recording_gains), nwb_recording_gains)

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_dtype(self, name, conversion_options):
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=2.0)

        nwbfile_path = str(self.savedir / f"test_neuroscope_dtype_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            output_dtype = nwbfile.acquisition["ElectricalSeriesRaw"].data.dtype
            self.assertEqual(first=output_dtype, second=np.dtype("int16"))

    def test_neuroscope_starting_time(self):
        nwbfile_path = str(self.savedir / "testing_start_time.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(
            source_data=dict(TestRecording=dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat")))
        )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        starting_time = 123.0
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=dict(TestRecording=dict(starting_time=starting_time)),
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            self.assertEqual(first=starting_time, second=nwbfile.acquisition["ElectricalSeriesRaw"].starting_time)


if __name__ == "__main__":
    unittest.main()
