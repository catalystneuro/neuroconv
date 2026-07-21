"""Tests for VameInterface using VAME project output data."""

import json
import re
import warnings
from datetime import datetime

import numpy as np
import pytest
import yaml
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import NWBConverter
from neuroconv.datainterfaces import VameInterface
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface

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


def _write_minimal_config(tmp_path, **fields):
    """Write a minimal VAME config.yaml with the given fields and return its path."""
    config = {"project_name": "unit_test_project", **fields}
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


class TestVameInterfaceMinimal(DataInterfaceTestMixin):
    """VameInterface with a single motif series and no optional inputs."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame = metadata["Behavior"]["Vame"]
        assert vame["VameProjects"]["VAMEProject"]["name"] == "VAMEProject"
        assert "VAMEProject_motif_kmeans" in vame["MotifSeries"]
        assert vame["MotifSeries"]["VAMEProject_motif_kmeans"]["algorithm"] == "kmeans"
        assert "LatentSpaceSeries" not in vame
        assert "CommunitySeries" not in vame

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            config = json.loads(project.vame_config)
            assert config["project_name"] == "my_vame_project"
            assert project.latent_space_series is None
            assert len(project.community_series) == 0
            assert_array_equal(
                project.motif_series["MotifSeriesKmeans"].data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )


class TestVameInterfaceFull(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """VameInterface with all optional inputs: latent vectors, community labels, config."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        latent_vectors_file_path=str(LATENT_VECTORS_PATH),
        community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame = metadata["Behavior"]["Vame"]
        assert vame["VameProjects"]["VAMEProject"]["name"] == "VAMEProject"
        assert "VAMEProject_motif_kmeans" in vame["MotifSeries"]
        assert vame["MotifSeries"]["VAMEProject_motif_kmeans"]["algorithm"] == "kmeans"
        assert "30 dimensions" in vame["LatentSpaceSeries"]["VAMEProject_latent_space"]["description"]
        community = vame["CommunitySeries"]["VAMEProject_community_kmeans"]
        assert community["motif_series_metadata_key"] == "VAMEProject_motif_kmeans"
        assert community["algorithm"] == "kmeans"

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert_array_equal(
                project.motif_series["MotifSeriesKmeans"].data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project.latent_space_series.data[:],
                np.load(LATENT_VECTORS_PATH).astype(np.float32),
            )
            assert_array_equal(
                project.community_series["CommunitySeriesKmeans"].data[:],
                np.load(COMMUNITY_LABELS_PATH).astype(np.int32),
            )
            config = json.loads(project.vame_config)
            assert config["project_name"] == "my_vame_project"
            assert config["n_clusters"] == 15


class TestVameInterfaceWithStubTest(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """VameInterface with stub_test=True to verify frame truncation."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        latent_vectors_file_path=str(LATENT_VECTORS_PATH),
        community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
        sampling_frequency_hz=30.0,
    )
    conversion_options = dict(stub_test=True)
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame = metadata["Behavior"]["Vame"]
        assert vame["VameProjects"]["VAMEProject"]["name"] == "VAMEProject"
        assert "VAMEProject_motif_kmeans" in vame["MotifSeries"]
        assert "LatentSpaceSeries" in vame
        assert "CommunitySeries" in vame

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert len(project.motif_series["MotifSeriesKmeans"].data[:]) == 100
            assert len(project.latent_space_series.data[:]) == 100
            assert len(project.community_series["CommunitySeriesKmeans"].data[:]) == 100


class TestVameInterfaceMultipleAlgorithms(DataInterfaceTestMixin):
    """Single VameInterface with two MotifSeries (kmeans + hmm) in one VAMEProject."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_paths={
            "kmeans": str(MOTIF_LABELS_PATH),
            "hmm": str(HMM_LABELS_PATH),
        },
        latent_vectors_file_path=str(LATENT_VECTORS_PATH),
        community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame = metadata["Behavior"]["Vame"]
        assert "VAMEProject_motif_kmeans" in vame["MotifSeries"]
        assert "VAMEProject_motif_hmm" in vame["MotifSeries"]
        assert "VAMEProject_community_kmeans" in vame["CommunitySeries"]
        assert (
            vame["CommunitySeries"]["VAMEProject_community_kmeans"]["motif_series_metadata_key"]
            == "VAMEProject_motif_kmeans"
        )

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert len(project.motif_series) == 2
            motif_series_kmeans = project.motif_series["MotifSeriesKmeans"]
            assert_array_equal(
                motif_series_kmeans.data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project.motif_series["MotifSeriesHmm"].data[:],
                np.load(HMM_LABELS_PATH).astype(np.int32),
            )
            assert len(project.community_series) == 1
            community_series_kmeans = project.community_series["CommunitySeriesKmeans"]
            assert community_series_kmeans.motif_series == motif_series_kmeans
            assert_array_equal(
                community_series_kmeans.data[:],
                np.load(COMMUNITY_LABELS_PATH).astype(np.int32),
            )


class TestVameInterfaceAutoDiscoverFilePaths(DataInterfaceTestMixin):
    """VameInterface with session_name auto-discovers all paths from the config."""

    data_interface_cls = VameInterface
    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        session_name=_SESSION_STEM,
        sampling_frequency_hz=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        vame = metadata["Behavior"]["Vame"]
        assert "VAMEProject_motif_kmeans" in vame["MotifSeries"]
        assert "VAMEProject_motif_hmm" in vame["MotifSeries"]
        assert "LatentSpaceSeries" in vame
        assert "VAMEProject_community_kmeans" in vame["CommunitySeries"]
        assert (
            vame["CommunitySeries"]["VAMEProject_community_kmeans"]["motif_series_metadata_key"]
            == "VAMEProject_motif_kmeans"
        )

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
            assert len(project.motif_series) == 2
            assert_array_equal(
                project.motif_series["MotifSeriesKmeans"].data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project.motif_series["MotifSeriesHmm"].data[:],
                np.load(HMM_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project.latent_space_series.data[:],
                np.load(LATENT_VECTORS_PATH).astype(np.float32),
            )
            assert len(project.community_series) == 1


class TestVameInterfaceEthogram:
    """The curated ndx-ethogram products (EthogramBouts + Ethogram) derived from each MotifSeries."""

    interface_kwargs = dict(
        file_path=str(CONFIG_PATH),
        motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
        sampling_frequency_hz=30.0,
    )

    def test_metadata_has_ethogram_entries(self):
        ethograms = VameInterface(**self.interface_kwargs).get_metadata()["Behavior"]["Ethograms"]
        assert ethograms["VAMEProject_kmeans"]["EthogramBouts"]["name"] == "VAMEProjectEthogramBoutsKmeans"
        assert ethograms["VAMEProject_kmeans"]["Ethogram"]["name"] == "VAMEProjectEthogramKmeans"

    def test_bouts_are_motif_labels_run_length_encoded(self):
        interface = VameInterface(**self.interface_kwargs)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata=interface.get_metadata())
        bouts = nwbfile.processing["behavior"]["VAMEProjectEthogramBoutsKmeans"]
        labels = np.load(MOTIF_LABELS_PATH).astype(np.int32)
        run_starts = np.concatenate(([0], np.flatnonzero(np.diff(labels)) + 1))
        # One row per maximal run; the label is that run's motif id as text.
        assert len(bouts) == len(run_starts)
        assert list(bouts["label"][:]) == [str(int(labels[index])) for index in run_starts]
        # Gapless, strictly increasing single-label partition.
        start_times = np.asarray(bouts["start_time"][:])
        stop_times = np.asarray(bouts["stop_time"][:])
        assert np.all(np.diff(start_times) > 0)
        assert np.allclose(stop_times[:-1], start_times[1:])
        assert bouts.labeling_method == "automated"
        assert bouts.source_software.startswith("VAME")

    def test_catalogue_covers_full_cluster_space_with_community_category(self):
        interface = VameInterface(**self.interface_kwargs)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata=interface.get_metadata())
        catalogue = nwbfile.processing["behavior"]["VAMEProjectEthogramKmeans"]
        assert len(catalogue) == 15  # n_clusters from config, including motifs absent this session.
        assert catalogue.exclusive
        assert list(catalogue["behavior"][:]) == [str(index) for index in range(15)]
        assert [int(code) for code in catalogue["native_code"][:]] == list(range(15))
        # category = the modal community per motif, matching an independent computation.
        motif_labels = np.load(MOTIF_LABELS_PATH)
        community_labels = np.load(COMMUNITY_LABELS_PATH)
        for motif_id in range(15):
            frames = motif_labels == motif_id
            expected_category = ""
            if frames.any():
                values, counts = np.unique(community_labels[frames], return_counts=True)
                expected_category = str(int(values[counts.argmax()]))
            assert catalogue["category"][motif_id] == expected_category

    def test_bouts_link_to_source_motif_series_and_catalogue(self):
        interface = VameInterface(**self.interface_kwargs)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata=interface.get_metadata())
        behavior = nwbfile.processing["behavior"]
        bouts = behavior["VAMEProjectEthogramBoutsKmeans"]
        assert bouts.source is behavior["VAMEProject"].motif_series["MotifSeriesKmeans"]
        assert bouts.ethogram is behavior["VAMEProjectEthogramKmeans"]

    def test_roundtrip_preserves_bouts_and_catalogue(self, tmp_path):
        interface = VameInterface(**self.interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1).astimezone()
        path = tmp_path / "vame_ethogram.nwb"
        interface.run_conversion(nwbfile_path=str(path), metadata=metadata, overwrite=True)
        labels = np.load(MOTIF_LABELS_PATH).astype(np.int32)
        expected_runs = len(np.flatnonzero(np.diff(labels))) + 1
        with NWBHDF5IO(path=str(path), mode="r", load_namespaces=True) as io:
            behavior = io.read().processing["behavior"]
            bouts = behavior["VAMEProjectEthogramBoutsKmeans"]
            assert len(bouts) == expected_runs
            assert bouts.source.name == "MotifSeriesKmeans"
            assert behavior["VAMEProjectEthogramKmeans"].exclusive

    def test_layers_faithful_writes_project_without_ethogram(self):
        interface = VameInterface(**self.interface_kwargs)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile, metadata=interface.get_metadata(), layers="faithful")
        behavior = nwbfile.processing["behavior"]
        assert "VAMEProject" in behavior.data_interfaces
        assert "VAMEProjectEthogramBoutsKmeans" not in behavior.data_interfaces
        assert "VAMEProjectEthogramKmeans" not in behavior.data_interfaces

    def test_layers_curated_writes_ethogram_without_project_and_drops_source(self, tmp_path):
        # curated-only: the faithful MotifSeries is absent, so the bouts' source back-link is dropped
        # to None. A source-less ndx-ethogram must still be a valid, writable file, hence the roundtrip.
        interface = VameInterface(**self.interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1).astimezone()
        path = tmp_path / "vame_curated.nwb"
        interface.run_conversion(nwbfile_path=str(path), metadata=metadata, overwrite=True, layers="curated")
        with NWBHDF5IO(path=str(path), mode="r", load_namespaces=True) as io:
            behavior = io.read().processing["behavior"]
            assert "VAMEProject" not in behavior.data_interfaces
            bouts = behavior["VAMEProjectEthogramBoutsKmeans"]
            assert bouts.source is None
            assert behavior["VAMEProjectEthogramKmeans"].exclusive


class TestVameInterfaceGetAvailableSessions:
    """VameInterface.get_available_sessions reads session names from config.yaml."""

    def test_returns_session_names_from_config(self):
        sessions = VameInterface.get_available_sessions(str(CONFIG_PATH))
        assert isinstance(sessions, list)
        assert _SESSION_STEM in sessions

    def test_returns_empty_list_when_field_absent(self, tmp_path):
        config_path = _write_minimal_config(tmp_path)
        assert VameInterface.get_available_sessions(str(config_path)) == []


class TestVameInterfaceAutoDiscoverFilePathsWarnings:
    """Warning conditions in _autodiscover_file_paths."""

    def test_warns_when_vame_version_missing(self, tmp_path):
        # segmentation_algorithms/n_clusters present and motif_labels_file_paths passed explicitly
        # so the only warning raised is about the missing 'vame_version' field.
        config_path = _write_minimal_config(tmp_path, segmentation_algorithms=["kmeans"], n_clusters=15)
        expected_message = (
            "The VAME config does not contain a 'vame_version' field. "
            "Auto-discovery of file paths has only been verified for VAME >= "
            f"{VameInterface._AUTODISCOVER_MIN_VAME_VERSION}. Results may be incorrect for older versions."
        )
        with pytest.warns(UserWarning, match=expected_message):
            VameInterface(
                file_path=str(config_path),
                session_name="my_session",
                motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
                sampling_frequency_hz=30.0,
            )

    def test_warns_when_vame_version_too_old(self, tmp_path):
        config_path = _write_minimal_config(
            tmp_path,
            vame_version="0.10.0",
            segmentation_algorithms=["kmeans"],
            n_clusters=15,
        )
        expected_message = (
            f"VAME version 0.10.0 is older than {VameInterface._AUTODISCOVER_MIN_VAME_VERSION}. "
            "Auto-discovery of file paths has only been verified for VAME >= "
            f"{VameInterface._AUTODISCOVER_MIN_VAME_VERSION} and may not work correctly for this version."
        )
        with pytest.warns(UserWarning, match=expected_message):
            VameInterface(
                file_path=str(config_path),
                session_name="my_session",
                motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
                sampling_frequency_hz=30.0,
            )

    def test_warns_when_segmentation_algorithms_missing(self, tmp_path):
        # n_clusters present but segmentation_algorithms absent
        config_path = _write_minimal_config(tmp_path, vame_version="0.13.0", n_clusters=15)
        expected_message = (
            "Cannot auto-discover VAME file paths: 'segmentation_algorithms' or 'n_clusters' "
            "is missing from config.yaml. Provide file paths explicitly."
        )
        with pytest.warns(UserWarning, match=expected_message):
            VameInterface(
                file_path=str(config_path),
                session_name="my_session",
                sampling_frequency_hz=30.0,
            )

    def test_warns_when_n_clusters_missing(self, tmp_path):
        # segmentation_algorithms present but n_clusters absent
        config_path = _write_minimal_config(tmp_path, vame_version="0.13.0", segmentation_algorithms=["kmeans"])
        expected_message = (
            "Cannot auto-discover VAME file paths: 'segmentation_algorithms' or 'n_clusters' "
            "is missing from config.yaml. Provide file paths explicitly."
        )
        with pytest.warns(UserWarning, match=expected_message):
            VameInterface(
                file_path=str(config_path),
                session_name="my_session",
                sampling_frequency_hz=30.0,
            )

    def test_warns_when_no_motif_files_found(self):
        # Valid config, but the requested session does not exist under results/.
        session_name = "nonexistent_session"
        session_vame_dir = VAME_DATA_PATH / "results" / session_name / "VAME"
        expected_message = (
            f"No motif label files were found for session '{session_name}' under '{session_vame_dir}'. "
            "Provide motif_labels_file_paths explicitly if the files are in a non-standard location."
        )
        with pytest.warns(UserWarning, match=re.escape(expected_message)):
            VameInterface(
                file_path=str(CONFIG_PATH),
                session_name=session_name,
                sampling_frequency_hz=30.0,
            )

    def test_explicit_paths_suppress_motif_discovery(self):
        """When motif_labels_file_paths is passed explicitly, no motif-discovery warning is raised."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            interface = VameInterface(
                file_path=str(CONFIG_PATH),
                session_name="nonexistent_session",
                motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
                sampling_frequency_hz=30.0,
            )
        # Explicit path was honoured
        assert "kmeans" in interface._motif_labels_file_paths


class TestVameInterfaceGetOriginalTimestamps:
    """Verify that get_original_timestamps() applies the time_window/2 offset, and test for edge cases."""

    def test_starting_time_offset(self):
        sampling_frequency_hz = 30.0
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
            sampling_frequency_hz=sampling_frequency_hz,
        )
        timestamps = interface.get_original_timestamps()
        expected_offset = 0.5
        assert timestamps[0] == expected_offset, f"Expected starting time {expected_offset}, got {timestamps[0]}"

    def test_no_time_window_in_config(self, tmp_path):
        """When time_window is absent from config the offset is zero."""
        config_path = _write_minimal_config(tmp_path, zdims=10)

        sampling_frequency_hz = 10.0
        interface = VameInterface(
            file_path=str(config_path),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
            sampling_frequency_hz=sampling_frequency_hz,
        )
        timestamps = interface.get_original_timestamps()
        assert timestamps[0] == 0.0

    def test_raises_when_no_sampling_frequency(self):
        """Without sampling_frequency_hz, get_original_timestamps() cannot compute timestamps."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        with pytest.raises(ValueError, match="sampling_frequency_hz"):
            interface.get_original_timestamps()

    def test_uses_latent_vectors_when_no_motif_labels(self):
        """Falls back to the latent vector file for frame count when no motif labels are provided."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            latent_vectors_file_path=str(LATENT_VECTORS_PATH),
            sampling_frequency_hz=30.0,
        )
        timestamps = interface.get_original_timestamps()
        assert len(timestamps) == len(np.load(LATENT_VECTORS_PATH))

    def test_uses_community_labels_when_no_motif_or_latent(self):
        """Falls back to the community label file for frame count when neither motif nor latent is available."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
            sampling_frequency_hz=30.0,
        )
        timestamps = interface.get_original_timestamps()
        assert len(timestamps) == len(np.load(COMMUNITY_LABELS_PATH))

    def test_raises_when_no_data_files(self):
        """Raises an informative error when neither motif labels, latent vectors, nor community labels are set."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            sampling_frequency_hz=30.0,
        )
        with pytest.raises(ValueError, match="without any data file"):
            interface.get_original_timestamps()

    def test_get_timestamps_returns_aligned_when_set(self):
        """get_timestamps() returns the aligned timestamps set via set_aligned_timestamps()."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
            sampling_frequency_hz=30.0,
        )
        aligned = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        interface.set_aligned_timestamps(aligned)
        assert_array_equal(interface.get_timestamps(), aligned)


class TestVameInterfaceIrregularTimestamps:
    """When aligned timestamps are non-uniform, the NWB file stores explicit timestamps (not rate)."""

    def test_add_to_nwbfile_uses_timestamps_when_irregular(self):
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        # Non-uniform spacing -> calculate_regular_series_rate returns None
        irregular_timestamps = np.array([0.0, 0.1, 0.25, 0.4, 0.6])
        interface.set_aligned_timestamps(irregular_timestamps)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata(), stub_test=True)

        project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
        motif_series = project.motif_series["MotifSeriesKmeans"]
        assert_array_equal(motif_series.timestamps[:], irregular_timestamps)
        assert motif_series.rate is None


class TestVameInterfacePoseEstimationLink:
    """add_to_nwbfile links a VAMEProject to an existing PoseEstimation container."""

    def test_metadata_schema_permits_sibling_behavior_registries(self):
        """Behavior stays open for other interfaces' registries so a Video+VAME converter validates.

        VAME must not close its Behavior node, otherwise a sibling registry written by another
        behavior interface (e.g. a video interface's Behavior/InternalVideos) is rejected as an
        additional property when the combined metadata is validated against VAME's schema in a
        converter.
        """
        from neuroconv.utils.json_schema import validate_metadata

        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )

        behavior_metadata = dict(interface.get_metadata()["Behavior"])
        # A sibling registry another behavior interface would contribute (shape mirrors the video interfaces).
        behavior_metadata["InternalVideos"] = {"video_0": {"name": "Video0"}}
        behavior_schema = interface.get_metadata_schema()["properties"]["Behavior"]

        # Raises jsonschema.ValidationError if the Behavior node rejects the sibling key.
        validate_metadata(behavior_metadata, behavior_schema)

    def test_links_pose_estimation_when_key_is_set(self):
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        aligned_timestamps = np.arange(10, dtype=float)
        interface.set_aligned_timestamps(aligned_timestamps)

        # Build NWB file with a PoseEstimation container already present
        pose_estimation_interface = MockPoseEstimationInterface(num_samples=10, num_nodes=3, seed=0)
        pose_estimation_interface.set_aligned_timestamps(aligned_timestamps)
        pose_metadata = pose_estimation_interface.get_metadata()
        nwbfile = mock_NWBFile()
        pose_estimation_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=pose_metadata)

        pose_key = pose_estimation_interface.metadata_key
        pose_container_name = pose_metadata["Pose"]["PoseEstimations"][pose_key]["name"]

        vame_metadata = interface.get_metadata()
        # The pose registry must be present for the key to resolve (strict lookup, no name fallback).
        vame_metadata["Pose"] = pose_metadata["Pose"]
        vame_metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = pose_key
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=vame_metadata, stub_test=True)

        project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
        assert project.pose_estimation is not None
        assert project.pose_estimation.name == pose_container_name

    def test_links_pose_estimation_when_key_and_name_differ(self):
        """Registry key and NWB container name can differ — VameInterface resolves via Pose registry."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        aligned_timestamps = np.arange(10, dtype=float)
        interface.set_aligned_timestamps(aligned_timestamps)

        pose_interface = MockPoseEstimationInterface(num_samples=10, num_nodes=3, seed=0, metadata_key="DLC")
        pose_interface.set_aligned_timestamps(aligned_timestamps)
        pose_meta = pose_interface.get_metadata()
        pose_meta["Pose"]["PoseEstimations"]["DLC"]["name"] = "PoseEstimationDeepLabCut"

        nwbfile = mock_NWBFile()
        pose_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=pose_meta)

        vame_metadata = interface.get_metadata()
        vame_metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = "DLC"
        vame_metadata["Pose"] = pose_meta["Pose"]
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=vame_metadata, stub_test=True)

        project = nwbfile.processing["behavior"].data_interfaces["VAMEProject"]
        assert project.pose_estimation is not None
        assert project.pose_estimation.name == "PoseEstimationDeepLabCut"

    def test_ethogram_bouts_link_to_source_pose(self):
        """Each EthogramBouts links to the project's PoseEstimation via source_pose."""
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        aligned_timestamps = np.arange(10, dtype=float)
        interface.set_aligned_timestamps(aligned_timestamps)

        pose_interface = MockPoseEstimationInterface(num_samples=10, num_nodes=3, seed=0)
        pose_interface.set_aligned_timestamps(aligned_timestamps)
        pose_metadata = pose_interface.get_metadata()
        nwbfile = mock_NWBFile()
        pose_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=pose_metadata)
        pose_key = pose_interface.metadata_key

        vame_metadata = interface.get_metadata()
        vame_metadata["Pose"] = pose_metadata["Pose"]
        vame_metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = pose_key
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=vame_metadata, stub_test=True)

        behavior = nwbfile.processing["behavior"]
        pose_estimation = behavior.data_interfaces["VAMEProject"].pose_estimation
        assert pose_estimation is not None
        assert behavior["VAMEProjectEthogramBoutsKmeans"].source_pose is pose_estimation


class TestVameInterfaceVideoLink:
    """add_to_nwbfile links each EthogramBouts to an existing video ImageSeries via source_video."""

    def test_ethogram_bouts_link_to_video_resolved_through_registry(self):
        """video_metadata_key resolves through the video registry (key differs from ImageSeries name)."""
        from pynwb.image import ImageSeries

        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        interface.set_aligned_timestamps(np.arange(10, dtype=float))

        # An ImageSeries whose name differs from its registry key must already be in the file.
        nwbfile = mock_NWBFile()
        image_series = ImageSeries(
            name="BehaviorCameraVideo",
            external_file=["behavior.mp4"],
            format="external",
            starting_frame=[0],
            rate=30.0,
            num_samples=10,
            unit="n.a.",
        )
        nwbfile.add_acquisition(image_series)

        vame_metadata = interface.get_metadata()
        vame_metadata["Behavior"]["ExternalVideos"] = {"my_video": {"name": "BehaviorCameraVideo"}}
        vame_metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["video_metadata_key"] = "my_video"
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=vame_metadata, stub_test=True)

        bouts = nwbfile.processing["behavior"]["VAMEProjectEthogramBoutsKmeans"]
        assert bouts.source_video is image_series


class TestVameInterfaceStrictKeyResolution:
    """Unregistered *_metadata_key values raise, rather than silently falling back or dropping."""

    def _interface(self):
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
        )
        interface.set_aligned_timestamps(np.arange(10, dtype=float))
        return interface

    def test_unregistered_pose_key_raises(self):
        interface = self._interface()
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = "not_a_key"
        with pytest.raises(ValueError, match="pose_estimation_metadata_key 'not_a_key' was not found"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, stub_test=True)

    def test_unregistered_video_key_raises(self):
        interface = self._interface()
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        metadata["Behavior"]["Vame"]["VameProjects"]["VAMEProject"]["video_metadata_key"] = "not_a_key"
        with pytest.raises(ValueError, match="video_metadata_key 'not_a_key' was not found"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, stub_test=True)

    def test_unmatched_community_motif_link_raises(self):
        interface = VameInterface(
            file_path=str(CONFIG_PATH),
            motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
            community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
        )
        interface.set_aligned_timestamps(np.arange(10, dtype=float))
        nwbfile = mock_NWBFile()
        metadata = interface.get_metadata()
        community_key = next(iter(metadata["Behavior"]["Vame"]["CommunitySeries"]))
        metadata["Behavior"]["Vame"]["CommunitySeries"][community_key]["motif_series_metadata_key"] = "not_a_key"
        with pytest.raises(ValueError, match="motif_series_metadata_key 'not_a_key'"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, stub_test=True)


class TestVameInterfaceGetPoseEstimation:
    """Static method _get_pose_estimation raises informative errors."""

    def test_raises_when_no_pose_estimation_containers_in_file(self):
        """Raises with 'No PoseEstimation containers exist' when the file is empty."""
        nwbfile = mock_NWBFile()
        with pytest.raises(ValueError, match="No PoseEstimation containers exist"):
            VameInterface._get_pose_estimation(nwbfile, "SomeName")

    def test_raises_listing_available_containers_when_wrong_name(self):
        """Lists available PoseEstimation containers in the error when the requested name is absent."""
        nwbfile = mock_NWBFile()
        pose_estimation_interface = MockPoseEstimationInterface(num_samples=10, num_nodes=3, seed=0)
        pose_estimation_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=pose_estimation_interface.get_metadata())

        with pytest.raises(ValueError, match=pose_estimation_interface.metadata_key):
            VameInterface._get_pose_estimation(nwbfile, "WrongName")

    def test_returns_container_when_name_matches(self):
        """Returns the PoseEstimation object when the name is found."""
        nwbfile = mock_NWBFile()
        pose_estimation_interface = MockPoseEstimationInterface(num_samples=10, num_nodes=3, seed=0)
        pose_estimation_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=pose_estimation_interface.get_metadata())

        expected = nwbfile.processing["behavior"].data_interfaces[pose_estimation_interface.metadata_key]
        result = VameInterface._get_pose_estimation(nwbfile, pose_estimation_interface.metadata_key)
        assert result is expected


class TestVameInterfacesInConverter:
    """Two VameInterface instances with different metadata_key values written to the same NWB file.

    Represents two completely separate VAME model trainings stored in one session file.
    """

    def test_two_vame_projects_in_nwbconverter(self, tmp_path):
        class TwoProjectConverter(NWBConverter):
            data_interface_classes = dict(ProjectA=VameInterface, ProjectB=VameInterface)

        source_data = dict(
            ProjectA=dict(
                file_path=str(CONFIG_PATH),
                motif_labels_file_paths={
                    "kmeans": str(MOTIF_LABELS_PATH),
                    "hmm": str(HMM_LABELS_PATH),
                },
                latent_vectors_file_path=str(LATENT_VECTORS_PATH),
                community_labels_file_paths={"kmeans": str(COMMUNITY_LABELS_PATH)},
                sampling_frequency_hz=30.0,
                metadata_key="ProjectA",
            ),
            ProjectB=dict(
                file_path=str(CONFIG_PATH),
                motif_labels_file_paths={"kmeans": str(MOTIF_LABELS_PATH)},
                sampling_frequency_hz=30.0,
                metadata_key="ProjectB",
            ),
        )
        converter = TwoProjectConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now().astimezone()

        nwbfile_path = tmp_path / "two_projects.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata)

        with NWBHDF5IO(path=str(nwbfile_path), mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            behavior = nwbfile.processing["behavior"].data_interfaces
            assert "ProjectA" in behavior
            assert "ProjectB" in behavior

            project_a = behavior["ProjectA"]
            assert len(project_a.motif_series) == 2
            assert_array_equal(
                project_a.motif_series["MotifSeriesKmeans"].data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project_a.motif_series["MotifSeriesHmm"].data[:],
                np.load(HMM_LABELS_PATH).astype(np.int32),
            )
            assert_array_equal(
                project_a.latent_space_series.data[:],
                np.load(LATENT_VECTORS_PATH).astype(np.float32),
            )
            assert len(project_a.community_series) == 1

            project_b = behavior["ProjectB"]
            assert len(project_b.motif_series) == 1
            assert_array_equal(
                project_b.motif_series["MotifSeriesKmeans"].data[:],
                np.load(MOTIF_LABELS_PATH).astype(np.int32),
            )
            assert project_b.latent_space_series is None
