from datetime import datetime, timezone

import pytest
from pynwb import NWBHDF5IO

from neuroconv.converters import TDTFiberPhotometryGuppyConverter
from neuroconv.tools.testing import generate_mock_guppy_output_folder
from neuroconv.utils import dict_deep_update

from ..setup_paths import OPHYS_DATA_PATH

# The GuPPy output folder is generated on the fly (see mock_guppy) rather than pulled from GIN. The
# only real data kept is the small (~1 MB) Photo_249 stubbed TDT tank -- already shared by the TDT
# fiber-photometry and events interface tests -- which supplies the authoritative session start
# time, stream names, and event epoc counts. The generator's default store/event names
# (Dv1A/Dv2A/Dv3B/Dv4B, LNRW/LNnR/PrtR) are exactly the ones this tank exposes, which is the only
# coupling the converter requires.
SESSION_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"


EXPECTED_RECORDING_SITES = ("dms", "dls")
EXPECTED_TDT_SESSION_START_TIME = datetime(2020, 7, 21, 17, 2, 24, 999999, tzinfo=timezone.utc)
# One single-series TDT acquisition interface (and one FiberPhotometryTable row) per GuPPy store.
EXPECTED_TDT_INTERFACE_NAMES = {
    "TDTFiberPhotometry_dms_signal",
    "TDTFiberPhotometry_dms_control",
    "TDTFiberPhotometry_dls_signal",
    "TDTFiberPhotometry_dls_control",
}
EXPECTED_RESPONSE_SERIES_NAMES = {"dms_signal", "dms_control", "dls_signal", "dls_control"}
# Onset counts from the Photo_249 epocs GuPPy listed (PrtR -> port_entries, etc.).
EXPECTED_EVENT_TO_COUNT = {"port_entries": 49, "unrewarded_nose_pokes": 1457, "rewarded_nose_pokes": 50}
MERGED_EVENTS_TABLE_NAME = "BehavioralEvents"

# The FiberPhotometry provenance chain is the user's to supply (see
# docs/developer_guide/fiber_photometry_metadata_structure.rst) -- no interface fabricates it. Row
# order here fixes the acquisition table layout the converter links the GuPPy recording sites to:
# dms signal/control first, then dls, i.e. rows 0-3.
DEVICE_METADATA = {
    "DeviceModels": {
        "optical_fiber_model": {
            "type": "OpticalFiberModel",
            "name": "optical_fiber_model",
            "manufacturer": "Doric Lenses",
            "numerical_aperture": 0.48,
        },
        "excitation_source_model": {
            "type": "ExcitationSourceModel",
            "name": "excitation_source_model",
            "manufacturer": "Doric Lenses",
            "source_type": "LED",
            "excitation_mode": "one-photon",
        },
        "photodetector_model": {
            "type": "PhotodetectorModel",
            "name": "photodetector_model",
            "manufacturer": "Doric Lenses",
            "detector_type": "photodiode",
        },
    },
    "Devices": {
        "optical_fiber_dms": {
            "type": "OpticalFiber",
            "name": "optical_fiber_dms",
            "device_model_metadata_key": "optical_fiber_model",
            "fiber_insertion": {"depth_in_mm": 2.8, "insertion_position_ap_in_mm": 0.8},
        },
        "optical_fiber_dls": {
            "type": "OpticalFiber",
            "name": "optical_fiber_dls",
            "device_model_metadata_key": "optical_fiber_model",
            "fiber_insertion": {"depth_in_mm": 3.5, "insertion_position_ap_in_mm": 0.1},
        },
        "excitation_source_465": {
            "type": "ExcitationSource",
            "name": "excitation_source_465",
            "device_model_metadata_key": "excitation_source_model",
        },
        "excitation_source_405": {
            "type": "ExcitationSource",
            "name": "excitation_source_405",
            "device_model_metadata_key": "excitation_source_model",
        },
        "photodetector": {
            "type": "Photodetector",
            "name": "photodetector",
            "device_model_metadata_key": "photodetector_model",
        },
    },
}
FIBER_PHOTOMETRY_METADATA = {
    "FiberPhotometryIndicators": {
        "gcamp": {"name": "gcamp", "label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
    },
    "FiberPhotometryTable": {
        "name": "fiber_photometry_table",
        "description": "Dual-site (DMS/DLS) dual-wavelength fiber photometry setup.",
        "rows": {
            "dms_signal": {
                "location": "DMS",
                "excitation_wavelength_in_nm": 465.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": "optical_fiber_dms",
                "excitation_source_metadata_key": "excitation_source_465",
                "photodetector_metadata_key": "photodetector",
            },
            "dms_control": {
                "location": "DMS",
                "excitation_wavelength_in_nm": 405.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": "optical_fiber_dms",
                "excitation_source_metadata_key": "excitation_source_405",
                "photodetector_metadata_key": "photodetector",
            },
            "dls_signal": {
                "location": "DLS",
                "excitation_wavelength_in_nm": 465.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": "optical_fiber_dls",
                "excitation_source_metadata_key": "excitation_source_465",
                "photodetector_metadata_key": "photodetector",
            },
            "dls_control": {
                "location": "DLS",
                "excitation_wavelength_in_nm": 405.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator_metadata_key": "gcamp",
                "optical_fiber_metadata_key": "optical_fiber_dls",
                "excitation_source_metadata_key": "excitation_source_405",
                "photodetector_metadata_key": "photodetector",
            },
        },
    },
}
# Each acquisition series points at its own row; the converter reads these regions to work out which
# rows belong to which GuPPy recording site.
SERIES_METADATA = {
    metadata_key: {
        "fiber_photometry_table_region": [metadata_key],
        "fiber_photometry_table_region_description": f"The {metadata_key} acquisition fiber.",
    }
    for metadata_key in ("dms_signal", "dms_control", "dls_signal", "dls_control")
}


class TestTDTFiberPhotometryGuppyConverter:
    @pytest.fixture
    def guppy_output_folder(self, tmp_path):
        return generate_mock_guppy_output_folder(tmp_path / "guppy_output")

    @pytest.fixture
    def converter(self, guppy_output_folder):
        return TDTFiberPhotometryGuppyConverter(
            tdt_folder_path=SESSION_FOLDER,
            guppy_folder_path=guppy_output_folder,
        )

    @pytest.fixture
    def metadata(self, converter):
        """The converter's metadata with the user-supplied FiberPhotometry provenance chain merged in."""
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, DEVICE_METADATA)
        metadata["FiberPhotometry"] = dict_deep_update(metadata["FiberPhotometry"], FIBER_PHOTOMETRY_METADATA)
        metadata["FiberPhotometry"] = dict_deep_update(metadata["FiberPhotometry"], SERIES_METADATA)
        return metadata

    def test_construction_creates_all_interfaces(self, converter):
        assert set(converter.data_interface_objects) == EXPECTED_TDT_INTERFACE_NAMES | {"TDTEvents", "Guppy"}

    def test_session_start_time_taken_from_tdt(self, converter):
        metadata = converter.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == EXPECTED_TDT_SESSION_START_TIME.isoformat()

    def test_metadata_preserves_guppy_schema(self, converter):
        metadata = converter.get_metadata()
        assert "Guppy" in metadata["FiberPhotometry"]
        guppy_metadata_key = converter.data_interface_objects["Guppy"].metadata_key
        guppy_metadata = metadata["FiberPhotometry"]["Guppy"][guppy_metadata_key]
        # Renamed away from the interface default of "fiber_photometry" to avoid colliding with the
        # TDT FiberPhotometry lab_meta_data object of the same name.
        assert guppy_metadata["ProcessingModule"]["name"] == "guppy"
        # Traces is a dict keyed by the derived object name.
        trace_names = set(guppy_metadata["Traces"].keys())
        assert {"dff_dms", "z_score_dms", "cntrl_sig_fit_dms", "dff_dls"}.issubset(trace_names)

    def test_metadata_schema_includes_both_subinterfaces(self, converter):
        schema = converter.get_metadata_schema()
        guppy_metadata_key = converter.data_interface_objects["Guppy"].metadata_key
        assert guppy_metadata_key in schema["properties"]["FiberPhotometry"]["properties"]["Guppy"]["properties"]

    def test_run_conversion_writes_acquisition_and_processing(self, converter, metadata, tmp_path):
        nwbfile_path = tmp_path / "tdt_guppy_converter.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True, stub_test=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time == EXPECTED_TDT_SESSION_START_TIME

            response_series_names = [
                name
                for name, obj in nwbfile.acquisition.items()
                if obj.neurodata_type == "FiberPhotometryResponseSeries"
            ]
            assert EXPECTED_RESPONSE_SERIES_NAMES == set(response_series_names)

            assert "guppy" in nwbfile.processing
            processing_module = nwbfile.processing["guppy"]
            recording_sites_table = processing_module["recording_sites"]
            assert recording_sites_table.neurodata_type == "GuppyRecordingSitesTable"
            assert list(recording_sites_table["recording_site"].data) == list(EXPECTED_RECORDING_SITES)
            assert processing_module["events"].neurodata_type == "GuppyEventsTable"

            # The converter authored the recording-sites registry with the acquisition fiber link:
            # each site's signal + control rows, in site order -> flat [0, 1, 2, 3].
            flat_fiber_indices = list(recording_sites_table["fiber_photometry_table_region"].target.data[:])
            assert flat_fiber_indices == [0, 1, 2, 3]

            recording_site_row = {site: index for index, site in enumerate(EXPECTED_RECORDING_SITES)}
            for recording_site in EXPECTED_RECORDING_SITES:
                for prefix in ("cntrl_sig_fit", "dff", "z_score"):
                    series_name = f"{prefix}_{recording_site}"
                    assert series_name in processing_module.data_interfaces
                    series = processing_module.data_interfaces[series_name]
                    # Derived traces are GuppyDerivedResponseSeries linked to the recording-site registry row;
                    # the acquisition provenance is reached through that row, not stamped on the series.
                    assert series.neurodata_type == "GuppyDerivedResponseSeries"
                    assert series.fiber_photometry_table_region is None
                    assert list(series.recording_site.data) == [recording_site_row[recording_site]]

            # Event-bearing products are concatenated across events into one object per condition: 8
            # PSTHs (2 sites x 2 features x {corrected, uncorrected}), 4 peak/AUCs, 2 cross-corrs.
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
        event_types = converter.get_metadata()["Events"][events_interface.metadata_key]["event_types"]
        # storesList.csv lists LNRW, LNnR, PrtR as the (non-fiber) event stores; only those propagate.
        epoc_name_to_event_name = {epoc_name: entry["event_name"] for epoc_name, entry in event_types.items()}
        assert epoc_name_to_event_name == {
            "LNRW": "rewarded_nose_pokes",
            "LNnR": "unrewarded_nose_pokes",
            "PrtR": "port_entries",
        }

    def test_run_conversion_merges_events_and_links_registry(self, converter, metadata, tmp_path):
        nwbfile_path = tmp_path / "tdt_guppy_events.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True, stub_test=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            # Every behavioral event type lands in ONE merged EventsTable with an event_type discriminator.
            assert set(nwbfile.events) == {MERGED_EVENTS_TABLE_NAME}
            merged = nwbfile.get_events_table(MERGED_EVENTS_TABLE_NAME)
            assert "event_type" in merged.colnames
            assert len(merged) == sum(EXPECTED_EVENT_TO_COUNT.values())

            # The GuppyEventsTable's events DTR references each type's occurrence rows in that merged table
            # (a precise row reference, not a whole-table object reference).
            events_table = nwbfile.processing["guppy"]["events"]
            for row_index, event_name in enumerate(events_table["event_name"].data):
                referenced = events_table["events"][row_index]  # DataFrame of the merged table's rows
                assert set(referenced["event_type"]) == {event_name}
                assert len(referenced) == EXPECTED_EVENT_TO_COUNT[event_name]

    def test_derive_recording_site_to_table_rows(self, converter, metadata):
        """Each recording site owns the table-row indices its series declared as their regions."""
        recording_site_to_rows = converter._derive_recording_site_to_table_rows(metadata)
        assert recording_site_to_rows == {"dms": [0, 1], "dls": [2, 3]}

    def test_missing_table_row_raises(self, converter, metadata):
        """A series referencing a row key the table does not define fails loudly."""
        del metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]["dms_signal"]
        with pytest.raises(AssertionError, match="not present"):
            converter._derive_recording_site_to_table_rows(metadata)

    def test_missing_table_region_raises(self, converter, metadata):
        """A series that declares no table region fails loudly rather than linking nothing."""
        del metadata["FiberPhotometry"]["dms_signal"]["fiber_photometry_table_region"]
        with pytest.raises(AssertionError, match="declares no 'fiber_photometry_table_region'"):
            converter._derive_recording_site_to_table_rows(metadata)

    def test_guppy_timestamps_in_nwb_are_native(self, converter, metadata, tmp_path):
        """GuPPy traces keep their native timestamps -- no cross-system offset is applied.

        GuPPy and TDT share the recording-start origin, so GuPPy's emitted timestamps already sit
        on the TDT clock. The first sample stays ~1s in (the lights-on delay) rather than being
        shoved to the TDT stream start (0.0).
        """
        nwbfile_path = tmp_path / "tdt_guppy_alignment.nwb"
        converter.run_conversion(nwbfile_path=str(nwbfile_path), metadata=metadata, overwrite=True, stub_test=True)

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            processing_module = nwbfile.processing["guppy"]
            for recording_site in EXPECTED_RECORDING_SITES:
                dff_series = processing_module.data_interfaces[f"dff_{recording_site}"]
                # The mock GuPPy timebase is regular (1.0 + arange(n) / 200 Hz), so it is written as
                # starting_time + rate. The 1 s lights-on delay is preserved rather than being shifted
                # to the TDT stream start of 0.0.
                assert dff_series.timestamps is None
                assert float(dff_series.starting_time) == pytest.approx(1.0)
                assert float(dff_series.rate) == pytest.approx(200.0)
