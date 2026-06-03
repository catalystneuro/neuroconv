"""Tests for VameInterface using VAME project output data."""

import json
from datetime import datetime

import numpy as np
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces import VameInterface
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


_SESSION_STEM = "Session001_DPI1DLC_resnet50_MLOF_PASC_Inhibitor_Cohort3Mar10shuffle1_700000"

VAME_DATA_PATH = BEHAVIOR_DATA_PATH / "vame" / "my_vame_project"
MOTIF_LABELS_PATH = (
    VAME_DATA_PATH / "results" / _SESSION_STEM / "VAME" / "kmeans-15" / f"15_kmeans_label_{_SESSION_STEM}.npy"
)
LATENT_VECTORS_PATH = VAME_DATA_PATH / "results" / _SESSION_STEM / "VAME" / "latent_vectors.npy"
COMMUNITY_LABELS_PATH = (
    VAME_DATA_PATH
    / "results"
    / _SESSION_STEM
    / "VAME"
    / "kmeans-15"
    / "community"
    / f"cohort_community_label_{_SESSION_STEM}.npy"
)
HMM_LABELS_PATH = VAME_DATA_PATH / "results" / _SESSION_STEM / "VAME" / "hmm-15" / f"15_hmm_label_{_SESSION_STEM}.npy"
CONFIG_PATH = VAME_DATA_PATH / "config.yaml"


class TestVameInterfaceMotifOnly(DataInterfaceTestMixin):
    """VameInterface with only motif labels (no optional inputs)."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_path=str(MOTIF_LABELS_PATH),
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame_meta = metadata["VAME"]["VAMEProject"]
        assert vame_meta["name"] == "VAMEProject"
        assert "algorithm" not in vame_meta["MotifSeries"]
        assert "LatentSpaceSeries" not in vame_meta
        assert "CommunitySeries" not in vame_meta

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            config = json.loads(project.vame_config)
            assert config["project_name"] == "my_vame_project"
            assert project.latent_space_series is None
            assert project.community_series is None
            assert_array_equal(project.motif_series.data[:], np.load(MOTIF_LABELS_PATH).astype(np.int32))


class TestVameInterfaceFull(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """VameInterface with all optional inputs: latent vectors, community labels, config."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        motif_labels_file_path=str(MOTIF_LABELS_PATH),
        latent_vectors_file_path=str(LATENT_VECTORS_PATH),
        community_labels_file_path=str(COMMUNITY_LABELS_PATH),
        file_path=str(CONFIG_PATH),
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame_meta = metadata["VAME"]["VAMEProject"]
        assert vame_meta["name"] == "VAMEProject"
        assert "algorithm" not in vame_meta["MotifSeries"]
        assert "30 dimensions" in vame_meta["LatentSpaceSeries"]["description"]
        assert "CommunitySeries" in vame_meta

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert_array_equal(project.motif_series.data[:], np.load(MOTIF_LABELS_PATH).astype(np.int32))
            assert_array_equal(project.latent_space_series.data[:], np.load(LATENT_VECTORS_PATH).astype(np.float32))
            assert_array_equal(project.community_series.data[:], np.load(COMMUNITY_LABELS_PATH).astype(np.int32))
            assert project.community_series.algorithm == "n/a"  # ndx-vame default; algorithm not set by interface
            config = json.loads(project.vame_config)
            assert config["project_name"] == "my_vame_project"
            assert config["n_clusters"] == 15


class TestVameInterfaceWithStubTest(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """VameInterface with stub_test=True to verify frame truncation."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        motif_labels_file_path=str(MOTIF_LABELS_PATH),
        latent_vectors_file_path=str(LATENT_VECTORS_PATH),
        community_labels_file_path=str(COMMUNITY_LABELS_PATH),
        file_path=str(CONFIG_PATH),
        sampling_frequency_hz=30.0,
    )
    conversion_options = dict(stub_test=True)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame_meta = metadata["VAME"]["VAMEProject"]
        assert vame_meta["name"] == "VAMEProject"
        assert "LatentSpaceSeries" in vame_meta
        assert "CommunitySeries" in vame_meta

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert len(project.motif_series.data[:]) == 100
            assert len(project.latent_space_series.data[:]) == 100
            assert len(project.community_series.data[:]) == 100


class TestVameInterfaceHmm(DataInterfaceTestMixin):
    """VameInterface with HMM-segmented motif labels."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_path=str(HMM_LABELS_PATH),
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame_meta = metadata["VAME"]["VAMEProject"]
        assert vame_meta["name"] == "VAMEProject"
        assert "LatentSpaceSeries" not in vame_meta
        assert "CommunitySeries" not in vame_meta

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert_array_equal(project.motif_series.data[:], np.load(HMM_LABELS_PATH).astype(np.int32))


class TestVameInterfaceTimestamps:
    """Verify that get_original_timestamps() applies the time_window/2 offset."""

    def test_starting_time_offset(self):
        sampling_frequency_hz = 30.0
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_path=str(MOTIF_LABELS_PATH),
            sampling_frequency_hz=sampling_frequency_hz,
        )
        timestamps = interface.get_original_timestamps()
        expected_offset = 0.5
        assert timestamps[0] == expected_offset, f"Expected starting time {expected_offset}, got {timestamps[0]}"

    def test_no_time_window_in_config(self, tmp_path):
        """When time_window is absent from config the offset is zero."""
        import yaml

        config = {"project_name": "test", "zdims": 10}
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))

        sampling_frequency_hz = 10.0
        interface = VameInterface(
            file_path=str(config_path),
            motif_labels_file_path=str(MOTIF_LABELS_PATH),
            sampling_frequency_hz=sampling_frequency_hz,
        )
        timestamps = interface.get_original_timestamps()
        assert timestamps[0] == 0.0


class TestTwoVameInterfaces:
    """Two VameInterface instances (k-means and HMM) written to the same NWB file via NWBConverter.

    This reflects the typical real-world scenario: latent vectors and config are shared between
    runs (both produced by the same trained model), while motif and community labels differ per
    segmentation algorithm. Each run gets its own VAMEProject container via metadata_key.
    """

    def test_two_vame_interfaces_in_nwbconverter(self, tmp_path):
        class TwoVameConverter(NWBConverter):
            data_interface_classes = dict(Kmeans=VameInterface, Hmm=VameInterface)

        source_data = dict(
            Kmeans=dict(
                file_path=str(CONFIG_PATH),
                motif_labels_file_path=str(MOTIF_LABELS_PATH),
                latent_vectors_file_path=str(LATENT_VECTORS_PATH),
                community_labels_file_path=str(COMMUNITY_LABELS_PATH),
                sampling_frequency_hz=30.0,
                metadata_key="KmeansRun",
            ),
            Hmm=dict(
                file_path=str(CONFIG_PATH),  # same project config
                motif_labels_file_path=str(HMM_LABELS_PATH),
                latent_vectors_file_path=str(LATENT_VECTORS_PATH),  # same model output
                sampling_frequency_hz=30.0,
                metadata_key="HmmRun",
            ),
        )
        converter = TwoVameConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "two_vame.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

        with NWBHDF5IO(path=str(nwbfile_path), mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            behavior = nwbfile.processing["behavior"].data_interfaces
            assert "KmeansRun" in behavior
            assert "HmmRun" in behavior
            kmeans = behavior["KmeansRun"]
            hmm = behavior["HmmRun"]
            assert_array_equal(kmeans.motif_series.data[:], np.load(MOTIF_LABELS_PATH).astype(np.int32))
            assert_array_equal(kmeans.latent_space_series.data[:], np.load(LATENT_VECTORS_PATH).astype(np.float32))
            assert_array_equal(kmeans.community_series.data[:], np.load(COMMUNITY_LABELS_PATH).astype(np.int32))
            assert_array_equal(hmm.motif_series.data[:], np.load(HMM_LABELS_PATH).astype(np.int32))
            assert_array_equal(hmm.latent_space_series.data[:], np.load(LATENT_VECTORS_PATH).astype(np.float32))
            assert hmm.community_series is None
