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

    def test_construction_creates_all_interfaces(self, converter):
        assert set(converter.data_interface_objects) == {"TDTFiberPhotometry", "TDTEvents", "Guppy"}

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
            # The registries anchor region/event identity for every GuPPy product.
            regions_table = processing_module["regions"]
            assert regions_table.neurodata_type == "GuppyRegionsTable"
            assert list(regions_table["region"].data) == list(EXPECTED_REGIONS)
            assert processing_module["events"].neurodata_type == "GuppyEventsTable"

            # GuPPy region -> acquisition table rows, auto-derived from the shared stream-name linkage.
            expected_region_to_indices = {"dms": [0, 1], "dls": [2, 3]}
            region_row = {region: index for index, region in enumerate(EXPECTED_REGIONS)}
            for region in EXPECTED_REGIONS:
                for prefix in ("cntrl_sig_fit", "dff", "z_score"):
                    series_name = f"{prefix}_{region}"
                    assert (
                        series_name in processing_module.data_interfaces
                    ), f"Expected {series_name} in fiber_photometry processing module."
                    series = processing_module.data_interfaces[series_name]
                    # Derived traces are GuppyDerivedResponseSeries (a FiberPhotometryResponseSeries subtype)
                    # linked both into the acquisition table and to the GuPPy regions registry row.
                    assert series.neurodata_type == "GuppyDerivedResponseSeries"
                    assert list(series.fiber_photometry_table_region.data[:]) == expected_region_to_indices[region]
                    assert list(series.region.data) == [region_row[region]]

            # Event-bearing products are concatenated across events into one object per condition: 8
            # PSTHs (2 regions x 2 features x {corrected, uncorrected}), 4 peak/AUCs, 2 cross-corrs.
            products_by_type = {}
            for product in processing_module.data_interfaces.values():
                products_by_type.setdefault(product.neurodata_type, []).append(product)
            assert len(products_by_type["GuppyPSTH"]) == 8
            assert len(products_by_type["GuppyPeakAUC"]) == 4
            assert len(products_by_type["GuppyCrossCorrelation"]) == 2

            # One concatenated PSTH spans all three events: the per-trial 'event' reference resolves
            # into the events registry, and 'mean' has one column per event.
            event_names = list(processing_module["events"]["event_name"].data)
            psth = processing_module["psth_dms_z_score"]
            assert psth.traces.shape[1] == len(psth.event.data)  # one per-trial event label per column
            assert set(event_names[index] for index in psth.event.data) == set(event_names)
            assert psth.mean.shape[1] == len(event_names)

    def test_events_derived_from_guppy_stores_list(self, converter):
        """Only the storesList.csv behavioral event stores propagate, with human-readable names."""
        events_interface = converter.data_interface_objects["TDTEvents"]
        event_columns = converter.get_metadata()["Events"][events_interface.metadata_key]["event_columns"]
        # storesList.csv lists LNRW, LNnR, PrtN as the (non-fiber) event stores; only those propagate.
        epoc_name_to_event_name = {epoc_name: column["column_name"] for epoc_name, column in event_columns.items()}
        assert epoc_name_to_event_name == {
            "LNRW": "rewarded_nose_pokes",
            "LNnR": "unrewarded_nose_pokes",
            "PrtN": "port_entries",
        }

    def test_run_conversion_writes_tdt_events(self, converter, metadata, tmp_path):
        nwbfile_path = tmp_path / "tdt_guppy_events.nwb"
        converter.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            # Only the storesList event stores are written to acquisition, with human-readable names.
            # Onset counts come from the corresponding Photo_63 epocs (PrtN=5, LNnR=35, LNRW=2).
            expected_event_to_length = {
                "port_entries": 5,
                "unrewarded_nose_pokes": 35,
                "rewarded_nose_pokes": 2,
            }
            for event_name, expected_length in expected_event_to_length.items():
                events = nwbfile.acquisition[event_name]
                assert events.neurodata_type == "Events"
                assert len(events.timestamps) == expected_length
            # Tank epocs absent from storesList.csv (PrtR, RNPS) are not propagated.
            assert "PrtR" not in nwbfile.acquisition
            assert "RNPS" not in nwbfile.acquisition

            # The GuPPy events registry's optional object reference resolves to those acquisition Events.
            events_table = nwbfile.processing["guppy"]["events"]
            registry_event_names = list(events_table["event_name"].data)
            for row_index, event_name in enumerate(registry_event_names):
                referenced = events_table["events"][row_index]
                assert referenced is nwbfile.acquisition[event_name]

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
