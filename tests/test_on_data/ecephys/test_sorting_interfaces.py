from datetime import datetime

import numpy as np
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
    CellExplorerSortingInterface,
    KiloSortSortingInterface,
    NeuralynxSortingInterface,
    NeuroScopeSortingInterface,
    PhySortingInterface,
    PlexonSortingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    SortingExtractorInterfaceTestMixin,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestBlackrockSortingInterface(SortingExtractorInterfaceTestMixin):
    data_interface_cls = BlackrockSortingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.nev"), sampling_frequency=30_000.0)

    associated_recording_cls = BlackrockRecordingInterface
    associated_recording_kwargs = dict(file_path=str(DATA_PATH / "blackrock" / "FileSpec2.3001.ns5"))

    save_directory = OUTPUT_PATH


import pytest


class TestCellExplorerSortingInterfaceBuzCode(SortingExtractorInterfaceTestMixin):
    """This corresponds to the Buzsaki old CellExplorerFormat or Buzcode format."""

    data_interface_cls = CellExplorerSortingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_1" / "20170311_684um_2088um_170311_134350.spikes.cellinfo.mat"
                )
            ),
            dict(
                file_path=str(DATA_PATH / "cellexplorer" / "dataset_2" / "20170504_396um_0um_merge.spikes.cellinfo.mat")
            ),
            dict(
                file_path=str(
                    DATA_PATH / "cellexplorer" / "dataset_3" / "20170519_864um_900um_merge.spikes.cellinfo.mat"
                )
            ),
        ],
        ids=["dataset_1", "dataset_2", "dataset_3"],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


class TestCellExplorerSortingInterface(SortingExtractorInterfaceTestMixin):
    """This corresponds to the Buzsaki new CellExplorerFormat where a session.mat file with rich metadata is provided."""

    data_interface_cls = CellExplorerSortingInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            dict(
                file_path=str(
                    DATA_PATH
                    / "cellexplorer"
                    / "dataset_4"
                    / "Peter_MS22_180629_110319_concat_stubbed"
                    / "Peter_MS22_180629_110319_concat_stubbed.spikes.cellinfo.mat"
                )
            ),
            dict(
                file_path=str(
                    DATA_PATH
                    / "cellexplorer"
                    / "dataset_4"
                    / "Peter_MS22_180629_110319_concat_stubbed_hdf5"
                    / "Peter_MS22_180629_110319_concat_stubbed_hdf5.spikes.cellinfo.mat"
                )
            ),
        ],
        ids=["mat", "hdf5"],
    )
    def setup_interface(self, request):
        self.test_name = request.node.callspec.id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def test_writing_channel_metadata(self, setup_interface):
        interface, test_name = setup_interface

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

        self.nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_{test_name}_channel.nwb")

        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(
            nwbfile_path=self.nwbfile_path,
            overwrite=True,
            metadata=metadata,
            write_ecephys_metadata=True,
        )

        # Test that the registered recording has the expected channel properties
        recording_extractor = interface.generate_recording_with_channel_metadata()
        for key, expected_value in expected_channel_properties_recorder.items():
            extracted_value = recording_extractor.get_channel_property(channel_id=channel_id, key=key)
            if key == "location":
                assert np.allclose(expected_value, extracted_value)
            else:
                assert expected_value == extracted_value

        # Test that the electrode table has the expected values
        with NWBHDF5IO(self.nwbfile_path, "r") as io:
            nwbfile = io.read()
            electrode_table = nwbfile.electrodes.to_dataframe()
            electrode_table_row = electrode_table.query(f"channel_name=='{channel_id}'").iloc[0]
            for key, value in expected_channel_properties_electrodes.items():
                assert electrode_table_row[key] == value


class TestNeuralynxSortingInterfaceCheetahV551(SortingExtractorInterfaceTestMixin):
    data_interface_cls = NeuralynxSortingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.5.1" / "original_data"), stream_id="0"
    )
    save_directory = OUTPUT_PATH


class TestNeuralynxSortingInterfaceCheetah563(SortingExtractorInterfaceTestMixin):
    data_interface_cls = NeuralynxSortingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "neuralynx" / "Cheetah_v5.6.3" / "original_data"), stream_id="0"
    )

    save_directory = OUTPUT_PATH


class TestNeuroScopeSortingInterface(SortingExtractorInterfaceTestMixin):
    data_interface_cls = NeuroScopeSortingInterface
    interface_kwargs = dict(
        folder_path=str(DATA_PATH / "neuroscope" / "dataset_1"),
        xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2015, 8, 31, 0, 0)


class TestNeuroScopeSortingInterfaceNoXMLSpecified(SortingExtractorInterfaceTestMixin):
    """Corresponding to issue https://github.com/NeurodataWithoutBorders/nwb-guide/issues/881."""

    data_interface_cls = NeuroScopeSortingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "neuroscope" / "dataset_1"))
    save_directory = OUTPUT_PATH

    # The XML is not found and so no metadata is extracted
    def check_extracted_metadata(self, metadata: dict):
        pass


class TestPhySortingInterface(SortingExtractorInterfaceTestMixin):
    data_interface_cls = PhySortingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["Ecephys"]["UnitProperties"] == [
            dict(name="n_spikes", description="Number of spikes recorded from each unit."),
            dict(name="fr", description="Average firing rate of each unit."),
            dict(name="depth", description="Estimated depth of each unit in micrometers."),
            dict(name="Amplitude", description="Per-template amplitudes, computed as the L2 norm of the template."),
            dict(
                name="ContamPct",
                description="Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process.",
            ),
            dict(
                name="KSLabel",
                description="Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory).",
            ),
            dict(name="original_cluster_id", description="Original cluster ID assigned by Kilosort."),
            dict(
                name="amp",
                description="For every template, the maximum amplitude of the template waveforms across all channels.",
            ),
            dict(name="ch", description="The channel label of the best channel, as defined by the user."),
            dict(name="sh", description="The shank label of the best channel."),
        ]

    def check_units_table_propagation(self):
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        nwbfile = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)

        # example data does not contain n_spikes, fr, depth, amp, ch, and sh
        assert (
            nwbfile.units["Amplitude"].description
            == "Per-template amplitudes, computed as the L2 norm of the template."
        )
        assert (
            nwbfile.units["ContamPct"].description
            == "Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process."
        )
        assert (
            nwbfile.units["KSLabel"].description
            == "Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory)."
        )
        assert nwbfile.units["original_cluster_id"].description == "Original cluster ID assigned by Kilosort."

    def run_custom_checks(self):
        self.check_units_table_propagation()


class TestKilosortSortingInterface(SortingExtractorInterfaceTestMixin):
    data_interface_cls = KiloSortSortingInterface
    interface_kwargs = dict(folder_path=str(DATA_PATH / "phy" / "phy_example_0"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["Ecephys"]["UnitProperties"] == [
            dict(name="n_spikes", description="Number of spikes recorded from each unit."),
            dict(name="fr", description="Average firing rate of each unit."),
            dict(name="depth", description="Estimated depth of each unit in micrometers."),
            dict(name="Amplitude", description="Per-template amplitudes, computed as the L2 norm of the template."),
            dict(
                name="ContamPct",
                description="Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process.",
            ),
            dict(
                name="KSLabel",
                description="Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory).",
            ),
            dict(name="original_cluster_id", description="Original cluster ID assigned by Kilosort."),
            dict(
                name="amp",
                description="For every template, the maximum amplitude of the template waveforms across all channels.",
            ),
            dict(name="ch", description="The channel label of the best channel, as defined by the user."),
            dict(name="sh", description="The shank label of the best channel."),
        ]

    def check_units_table_propagation(self):
        metadata = self.interface.get_metadata()
        if "session_start_time" not in metadata["NWBFile"]:
            metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        nwbfile = self.interface.create_nwbfile(metadata=metadata, **self.conversion_options)

        # example data does not contain n_spikes, fr, depth, amp, ch, and sh
        assert (
            nwbfile.units["Amplitude"].description
            == "Per-template amplitudes, computed as the L2 norm of the template."
        )
        assert (
            nwbfile.units["ContamPct"].description
            == "Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process."
        )
        assert (
            nwbfile.units["KSLabel"].description
            == "Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory)."
        )
        assert nwbfile.units["original_cluster_id"].description == "Original cluster ID assigned by Kilosort."

    def run_custom_checks(self):
        self.check_units_table_propagation()


class TestPlexonSortingInterface(SortingExtractorInterfaceTestMixin):
    data_interface_cls = PlexonSortingInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "plexon" / "File_plexon_2.plx"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2000, 10, 30, 15, 56, 56)
