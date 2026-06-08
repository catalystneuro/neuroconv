from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import TDTFiberPhotometryGuppyConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file

from ..setup_paths import OPHYS_DATA_PATH

SESSION_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_63_207-181030-103332"
GUPPY_OUTPUT_FOLDER = SESSION_FOLDER / "Photo_63_207-181030-103332_output_1"
FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "fiber_photometry_metadata.yaml"


EXPECTED_REGIONS = ("dms", "dls")
EXPECTED_TDT_SESSION_START_TIME = datetime(2018, 10, 30, 15, 33, 53, 999999, tzinfo=timezone.utc)


class TestTDTFiberPhotometryGuppyConverter:
    @pytest.fixture
    def converter(self):
        return TDTFiberPhotometryGuppyConverter(
            tdt_folder_path=SESSION_FOLDER,
            guppy_folder_path=GUPPY_OUTPUT_FOLDER,
        )

    @pytest.fixture
    def metadata(self, converter):
        editable_metadata = load_dict_from_file(FIBER_PHOTOMETRY_METADATA_FILE)
        merged_metadata = dict_deep_update(converter.get_metadata(), editable_metadata)
        # The Photo_63 fixture exposes Fi1r rather than Fi1d, so the YAML's CommandedVoltageSeries
        # entries are dropped to keep the metadata consistent with the available TDT streams.
        merged_metadata["Ophys"]["FiberPhotometry"].pop("CommandedVoltageSeries", None)
        for row in merged_metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["rows"]:
            row.pop("commanded_voltage_series", None)
        return merged_metadata

    def test_construction_creates_both_interfaces(self, converter):
        assert set(converter.data_interface_objects) == {"TDTFiberPhotometry", "Guppy"}

    def test_session_start_time_taken_from_tdt(self, converter):
        metadata = converter.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == EXPECTED_TDT_SESSION_START_TIME.isoformat()

    def test_metadata_preserves_guppy_schema(self, converter):
        metadata = converter.get_metadata()
        assert "Guppy" in metadata["Ophys"]
        guppy_metadata = metadata["Ophys"]["Guppy"]
        # Renamed away from the GuppyInterface default of "fiber_photometry" to avoid
        # colliding with the TDT FiberPhotometry lab_meta_data object of the same name.
        assert guppy_metadata["ProcessingModule"]["name"] == "guppy"
        trace_names = {trace["name"] for trace in guppy_metadata["Traces"]}
        assert {"dff_dms", "z_score_dms", "cntrl_sig_fit_dms", "dff_dls"}.issubset(trace_names)

    def test_metadata_schema_includes_both_subinterfaces(self, converter):
        schema = converter.get_metadata_schema()
        ophys_properties = schema["properties"]["Ophys"]["properties"]
        assert "Guppy" in ophys_properties

    def test_run_conversion_writes_acquisition_and_processing(self, converter, metadata, tmp_path):
        nwbfile_path = tmp_path / "tdt_guppy_converter.nwb"
        converter.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time == EXPECTED_TDT_SESSION_START_TIME

            response_series_names = [
                name
                for name, obj in nwbfile.acquisition.items()
                if obj.neurodata_type == "FiberPhotometryResponseSeries"
            ]
            assert {
                "dms_calcium_signal",
                "dms_isosbestic_control",
                "dls_calcium_signal",
                "dls_isosbestic_control",
            } == set(response_series_names)

            assert "guppy" in nwbfile.processing
            processing_module = nwbfile.processing["guppy"]
            # GuPPy region -> acquisition table rows, auto-derived from the shared stream-name linkage.
            expected_region_to_indices = {"dms": [0, 1], "dls": [2, 3]}
            for region in EXPECTED_REGIONS:
                for prefix in ("cntrl_sig_fit", "dff", "z_score"):
                    series_name = f"{prefix}_{region}"
                    assert (
                        series_name in processing_module.data_interfaces
                    ), f"Expected {series_name} in fiber_photometry processing module."
                    series = processing_module.data_interfaces[series_name]
                    # Derived traces are FiberPhotometryResponseSeries linked into the acquisition table,
                    # each pointing at both the excitation-signal and isosbestic-control rows for its region.
                    assert series.neurodata_type == "FiberPhotometryResponseSeries"
                    assert list(series.fiber_photometry_table_region.data[:]) == expected_region_to_indices[region]

    def test_derive_region_to_table_indices(self, converter, metadata):
        """The auto-join composes region -> store names -> stream_name -> table rows."""
        region_to_indices = converter._derive_region_to_table_indices(metadata)
        assert region_to_indices == {"dms": [0, 1], "dls": [2, 3]}

    def test_unmatched_stream_name_raises(self, converter, metadata):
        """A region whose stores match no response-series stream_name fails loudly."""
        for response_series in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]:
            response_series["stream_name"] = "does_not_exist"
        with pytest.raises(AssertionError, match="matched no FiberPhotometryResponseSeries"):
            converter._derive_region_to_table_indices(metadata)

    def test_guppy_timestamps_in_nwb_are_native(self, converter, metadata, tmp_path):
        """GuPPy traces keep their native timestamps -- no cross-system offset is applied.

        GuPPy and TDT share the recording-start origin, so GuPPy's emitted timestamps already sit
        on the TDT clock. The first sample stays ~1s in (the lights-on delay) rather than being
        shoved to the TDT stream start (0.0), which the old offset alignment did incorrectly.
        """
        nwbfile_path = tmp_path / "tdt_guppy_alignment.nwb"
        converter.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        guppy_interface = converter.data_interface_objects["Guppy"]
        native_region_to_timestamps = guppy_interface.get_original_timestamps()

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            processing_module = nwbfile.processing["guppy"]
            for region in EXPECTED_REGIONS:
                native_timestamps = native_region_to_timestamps[region]
                dff_series = processing_module.data_interfaces[f"dff_{region}"]
                assert dff_series.timestamps is not None, f"Expected timestamps on dff_{region}."
                written = np.asarray(dff_series.timestamps[:])
                np.testing.assert_allclose(written, native_timestamps[: written.shape[0]], atol=1e-9)
                # ~1s lights-on delay preserved, not shifted to the TDT stream start of 0.0.
                assert written[0] > 0.5
