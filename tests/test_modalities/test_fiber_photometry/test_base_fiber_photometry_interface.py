"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import re
from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_allclose, assert_array_equal
from pynwb import NWBHDF5IO, read_nwb

from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface


@pytest.fixture
def full_metadata():
    """A complete, hand-built fiber photometry metadata chain for two fibers at one excitation wavelength.

    Test data (not a public API): device models, devices, an indicator, a two-row ``FiberPhotometryTable``,
    and the response-series region — the full provenance a user would supply to write everything. Every
    interface written against it needs ``num_fibers=2`` to match those two rows.
    """
    interface = MockFiberPhotometryInterface(num_fibers=2)
    metadata = interface.get_metadata()
    metadata["DeviceModels"] = dict(
        optical_fiber_model=dict(
            type="OpticalFiberModel",
            name="optical_fiber_model",
            manufacturer="Doric Lenses",
            numerical_aperture=0.48,
        ),
        excitation_source_model=dict(
            type="ExcitationSourceModel",
            name="excitation_source_model",
            manufacturer="Doric Lenses",
            source_type="LED",
            excitation_mode="one-photon",
        ),
        photodetector_model=dict(
            type="PhotodetectorModel",
            name="photodetector_model",
            manufacturer="Doric Lenses",
            detector_type="photodiode",
        ),
    )
    metadata["Devices"] = dict(
        optical_fiber_dms=dict(
            type="OpticalFiber",
            name="optical_fiber_dms",
            device_model_metadata_key="optical_fiber_model",
            fiber_insertion=dict(depth_in_mm=4.0, insertion_position_ap_in_mm=3.0),
        ),
        optical_fiber_dls=dict(
            type="OpticalFiber",
            name="optical_fiber_dls",
            device_model_metadata_key="optical_fiber_model",
            fiber_insertion=dict(depth_in_mm=4.2, insertion_position_ap_in_mm=0.5),
        ),
        excitation_source=dict(
            type="ExcitationSource",
            name="excitation_source",
            device_model_metadata_key="excitation_source_model",
        ),
        photodetector=dict(
            type="Photodetector",
            name="photodetector",
            device_model_metadata_key="photodetector_model",
        ),
    )
    fiber_photometry_metadata = metadata["FiberPhotometry"]
    fiber_photometry_metadata["FiberPhotometryIndicators"] = dict(indicator=dict(name="indicator", label="GCaMP6s"))
    fiber_photometry_metadata["FiberPhotometryTable"] = dict(
        name="fiber_photometry_table",
        description="Each row describes a single fiber photometry trace.",
        rows=dict(
            dms=dict(
                location="DMS",
                excitation_wavelength_in_nm=465.0,
                emission_wavelength_in_nm=525.0,
                indicator_metadata_key="indicator",
                optical_fiber_metadata_key="optical_fiber_dms",
                excitation_source_metadata_key="excitation_source",
                photodetector_metadata_key="photodetector",
            ),
            dls=dict(
                location="DLS",
                excitation_wavelength_in_nm=465.0,
                emission_wavelength_in_nm=525.0,
                indicator_metadata_key="indicator",
                optical_fiber_metadata_key="optical_fiber_dls",
                excitation_source_metadata_key="excitation_source",
                photodetector_metadata_key="photodetector",
            ),
        ),
    )
    series_metadata = fiber_photometry_metadata[interface.metadata_key]
    series_metadata["description"] = "GCaMP6s recorded at 465 nm from two fibers, in DMS and DLS."
    series_metadata["fiber_photometry_table_region"] = ["dms", "dls"]
    series_metadata["fiber_photometry_table_region_description"] = (
        "The DMS and DLS fibers recorded at the 465 nm excitation wavelength."
    )
    return metadata


class TestMockFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    data_interface_cls = MockFiberPhotometryInterface
    interface_kwargs = dict(num_fibers=2)
    conversion_options = dict(stub_test=True, stub_samples=3)

    # Hand-supplied, not read back from the interface: one seeded standard-normal draw, two fibers wide.
    expected_response_series_data = np.array(
        [
            [0.1257302210933933, -0.1321048632913019],
            [0.6404226504432821, 0.10490011715303971],
            [-0.535669373161111, 0.36159505490948474],
        ]
    )
    expected_rate = 100.0
    expected_starting_time = 0.0

    def test_get_metadata_adds_no_provenance(self):
        # A synthetic source has no optical hardware, indicator, or table to describe, so the default
        # metadata fabricates none of it (see #1789) — only the response-series entry and the mock's
        # session start time. The full chain is supplied by the user when they want it.
        interface = MockFiberPhotometryInterface()
        Draft7Validator.check_schema(interface.get_metadata_schema())

        metadata = interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2020, 1, 1, tzinfo=timezone.utc)

        fiber_photometry_metadata = metadata["FiberPhotometry"]
        assert "FiberPhotometryTable" not in fiber_photometry_metadata
        assert "FiberPhotometryIndicators" not in fiber_photometry_metadata
        assert not metadata.get("Devices")
        assert not metadata.get("DeviceModels")

        # The series entry carries only a default name — no fabricated description, and no unit (unit is a
        # property of the data, supplied when the series is built, not editable metadata).
        series_metadata = fiber_photometry_metadata[interface.metadata_key]
        assert series_metadata["name"] == "FiberPhotometryResponseSeries"
        assert "unit" not in series_metadata
        assert "description" not in series_metadata

    def test_metadata_key_override(self):
        # An explicit metadata_key names the response-series entry instead of the stream-derived default.
        interface = MockFiberPhotometryInterface(metadata_key="my_series")
        assert interface.metadata_key == "my_series"
        assert "my_series" in interface.get_metadata()["FiberPhotometry"]

    def test_column_order_is_wavelength_major(self):
        # Which column a trace lands on is positional: np.concatenate(axis=1) preserves the wavelength
        # order and each wavelength contributes its fibers in a block, so the table region has to list
        # its rows in that same order. Nothing downstream re-derives it.
        interface = MockFiberPhotometryInterface(excitation_wavelengths_in_nm=[470.0, 560.0, 415.0])
        data = interface._read_response_data()

        assert interface.stream_names == ["470nm", "560nm", "415nm"]
        assert data.shape == (100, 3)
        for index, stream_name in enumerate(interface.stream_names):
            assert_array_equal(data[:, index], interface._get_stream_data(stream_name=stream_name))

    def test_multi_fiber_series_contributes_one_column_per_fiber(self):
        # Several fibers at one wavelength is the layout ndx-fiber-photometry recommends. That reads as
        # one 2-D source array, which skips the np.newaxis promotion in _read_response_data entirely.
        interface = MockFiberPhotometryInterface(num_fibers=4)
        stream_data = interface._get_stream_data(stream_name="470nm")
        assert stream_data.ndim == 2

        data = interface._read_response_data()
        assert data.shape == (100, 4)
        assert_array_equal(data, stream_data)

    def test_wavelengths_and_fibers_multiply_into_blocks(self):
        # Aggregating over the wavelength axis, which is legal only on a rig where the excitations share
        # a clock. Columns total wavelengths x fibers, laid out one contiguous fiber block per
        # wavelength rather than interleaved.
        interface = MockFiberPhotometryInterface(excitation_wavelengths_in_nm=[470.0, 415.0], num_fibers=3)
        data = interface._read_response_data()

        assert data.shape == (100, 6)
        assert_array_equal(data[:, :3], interface._get_stream_data(stream_name="470nm"))
        assert_array_equal(data[:, 3:], interface._get_stream_data(stream_name="415nm"))

    def test_empty_wavelengths_errors(self):
        expected_error = "excitation_wavelengths_in_nm must name at least one excitation wavelength."
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            MockFiberPhotometryInterface(excitation_wavelengths_in_nm=[])

    def test_zero_fibers_errors(self):
        with pytest.raises(ValueError, match=re.escape("num_fibers must be at least 1, got 0.")):
            MockFiberPhotometryInterface(num_fibers=0)

    def test_single_fiber_collapses_to_one_column(self):
        # A lone column is written as a 1-D series rather than an (N, 1) one.
        interface = MockFiberPhotometryInterface()
        nwbfile = interface.create_nwbfile()

        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100,)

    def test_fully_annotated_metadata_round_trips(self, tmp_path, full_metadata):
        # The fully annotated path: a complete provenance chain is supplied, and every piece of it must
        # survive a write/read cycle — device models, devices (with model links and fiber insertion), the
        # indicator, both table rows in full, the region, and the response series.
        interface = MockFiberPhotometryInterface(num_fibers=2)

        nwbfile_path = tmp_path / "fully_annotated.nwb"
        nwbfile = interface.create_nwbfile(metadata=full_metadata)
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()

            assert read_nwbfile.session_start_time == datetime(2020, 1, 1, tzinfo=timezone.utc)

            # Device models.
            optical_fiber_model = read_nwbfile.device_models["optical_fiber_model"]
            assert optical_fiber_model.manufacturer == "Doric Lenses"
            assert optical_fiber_model.numerical_aperture == 0.48
            excitation_source_model = read_nwbfile.device_models["excitation_source_model"]
            assert excitation_source_model.source_type == "LED"
            assert excitation_source_model.excitation_mode == "one-photon"
            assert read_nwbfile.device_models["photodetector_model"].detector_type == "photodiode"

            # Devices, their model links, and the optical fibers' insertions.
            assert set(read_nwbfile.devices) == {
                "optical_fiber_dms",
                "optical_fiber_dls",
                "excitation_source",
                "photodetector",
            }
            optical_fiber = read_nwbfile.devices["optical_fiber_dms"]
            assert optical_fiber.model.name == "optical_fiber_model"
            assert optical_fiber.fiber_insertion.depth_in_mm == 4.0
            assert optical_fiber.fiber_insertion.insertion_position_ap_in_mm == 3.0
            assert read_nwbfile.devices["optical_fiber_dls"].fiber_insertion.depth_in_mm == 4.2
            assert read_nwbfile.devices["excitation_source"].model.name == "excitation_source_model"
            assert read_nwbfile.devices["photodetector"].model.name == "photodetector_model"

            fiber_photometry = read_nwbfile.lab_meta_data["fiber_photometry"]

            # Indicator.
            indicators = fiber_photometry.fiber_photometry_indicators.indicators
            assert indicators["indicator"].label == "GCaMP6s"

            # Table: both rows in full, including the per-row device and indicator references.
            table = fiber_photometry.fiber_photometry_table
            assert len(table) == 2
            assert list(table["location"][:]) == ["DMS", "DLS"]
            assert_array_equal(table["excitation_wavelength_in_nm"][:], np.array([465.0, 465.0]))
            assert_array_equal(table["emission_wavelength_in_nm"][:], np.array([525.0, 525.0]))
            assert table["optical_fiber"][0].name == "optical_fiber_dms"
            assert table["optical_fiber"][1].name == "optical_fiber_dls"
            assert table["excitation_source"][0].name == "excitation_source"
            assert table["photodetector"][0].name == "photodetector"
            assert table["indicator"][0].label == "GCaMP6s"

            # Response series, referencing the DMS (row 0) and DLS (row 1) fibers.
            response_series = read_nwbfile.acquisition["FiberPhotometryResponseSeries"]
            assert response_series.name == "FiberPhotometryResponseSeries"
            assert response_series.description == "GCaMP6s recorded at 465 nm from two fibers, in DMS and DLS."
            assert response_series.unit == "a.u."
            assert response_series.data[:].shape == (100, 2)
            assert response_series.rate == pytest.approx(100.0)
            assert response_series.starting_time == 0.0
            assert list(response_series.fiber_photometry_table_region.data[:]) == [0, 1]

    def test_optical_fiber_without_model_round_trips(self, tmp_path, full_metadata):
        # The optical fiber's device model is optional: ndx-ophys-devices makes ``model`` an optional link,
        # and the canonical device helper already treats ``device_model_metadata_key`` as optional. Dropping
        # the fiber's model must still write the fiber, its fiber_insertion, and the rest of the chain.
        # This exercises the optical-fiber branch of add_fiber_photometry_devices with no model to resolve,
        # which previously raised ``KeyError: 'device_model_metadata_key'`` before writing anything.
        full_metadata["Devices"]["optical_fiber_dms"].pop("device_model_metadata_key")
        full_metadata["Devices"]["optical_fiber_dls"].pop("device_model_metadata_key")
        full_metadata["DeviceModels"].pop("optical_fiber_model")

        interface = MockFiberPhotometryInterface(num_fibers=2)
        nwbfile_path = tmp_path / "model_less_fiber.nwb"
        nwbfile = interface.create_nwbfile(metadata=full_metadata)
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()

            # The fiber is written with no model, but everything else about it survives.
            optical_fiber = read_nwbfile.devices["optical_fiber_dms"]
            assert optical_fiber.model is None
            assert optical_fiber.fiber_insertion.depth_in_mm == 4.0
            assert optical_fiber.fiber_insertion.insertion_position_ap_in_mm == 3.0

            # Only the fibers' model was dropped; the other two devices keep theirs.
            assert "optical_fiber_model" not in read_nwbfile.device_models
            assert read_nwbfile.devices["excitation_source"].model.name == "excitation_source_model"
            assert read_nwbfile.devices["photodetector"].model.name == "photodetector_model"

            # The row still references the fiber, and the response series still round-trips.
            table = read_nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert table["optical_fiber"][0].name == "optical_fiber_dms"
            assert read_nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100, 2)

    def test_only_devices_referenced_by_the_table_are_added(self, full_metadata):
        # Regression test for (#1881).
        full_metadata["Devices"]["camera"] = dict(name="Camera1", description="Another interface's camera.")
        full_metadata["DeviceModels"]["camera_model"] = dict(name="camera_model", manufacturer="Basler")

        nwbfile = MockFiberPhotometryInterface(num_fibers=2).create_nwbfile(metadata=full_metadata)

        assert "Camera1" not in nwbfile.devices
        assert "camera_model" not in nwbfile.device_models
        assert "optical_fiber_dms" in nwbfile.devices
        assert "optical_fiber_model" in nwbfile.device_models

    def test_metadata_template_sizes_the_table_to_the_traces(self):
        # One row per trace, measured from the data rather than fixed. The table region is positional, so
        # a hard-coded row count would silently mismatch every recording but the one it was written for.
        interface = MockFiberPhotometryInterface(num_fibers=3, metadata_key="calcium_signal")
        template = interface.get_metadata_template()

        rows_metadata = template["FiberPhotometry"]["FiberPhotometryTable"]["rows"]
        assert list(rows_metadata) == ["trace_0", "trace_1", "trace_2"]
        assert template["FiberPhotometry"]["calcium_signal"]["fiber_photometry_table_region"] == list(rows_metadata)

        # One fiber per row, since a fiber is what a column distinguishes; the rest of the chain is shared.
        optical_fiber_metadata_keys = [row["optical_fiber_metadata_key"] for row in rows_metadata.values()]
        assert optical_fiber_metadata_keys == ["optical_fiber_0", "optical_fiber_1", "optical_fiber_2"]
        assert {row["excitation_source_metadata_key"] for row in rows_metadata.values()} == {"excitation_source"}

    def test_metadata_template_blanks_only_what_the_source_cannot_answer(self):
        # The blanks are the checklist, so whatever the source does know has to survive into the template
        # instead of being blanked along with the rest, and every cross-reference has to resolve.
        interface = MockFiberPhotometryInterface(metadata_key="calcium_signal")
        template = interface.get_metadata_template()

        assert template["NWBFile"]["session_start_time"] == datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert template["FiberPhotometry"]["calcium_signal"]["name"] == "FiberPhotometryResponseSeries"

        row_metadata = template["FiberPhotometry"]["FiberPhotometryTable"]["rows"]["trace_0"]
        assert row_metadata["location"] is None
        assert row_metadata["excitation_wavelength_in_nm"] is None
        assert row_metadata["emission_wavelength_in_nm"] is None
        assert template["FiberPhotometry"]["FiberPhotometryIndicators"]["indicator"]["label"] is None

        assert row_metadata["indicator_metadata_key"] in template["FiberPhotometry"]["FiberPhotometryIndicators"]
        assert row_metadata["optical_fiber_metadata_key"] in template["Devices"]
        assert row_metadata["photodetector_metadata_key"] in template["Devices"]

    def test_metadata_template_does_not_blank_a_field_the_source_filled(self):
        # The merge direction, which nothing else pins: the template declares fields no interface reports
        # today, so a source that starts reporting one has to win over the blank rather than be overwritten
        # by it. No such interface exists yet, hence the subclass.
        class DescribingFiberPhotometryInterface(MockFiberPhotometryInterface):
            def get_metadata(self):
                metadata = super().get_metadata()
                metadata["FiberPhotometry"][self.metadata_key]["description"] = "Read from the source."
                return metadata

        interface = DescribingFiberPhotometryInterface(metadata_key="calcium_signal")

        template = interface.get_metadata_template()

        assert template["FiberPhotometry"]["calcium_signal"]["description"] == "Read from the source."

    def test_filled_metadata_template_round_trips(self, tmp_path):
        # The template is a scaffold to edit, so filling every blank it marks has to be enough to write a
        # file, with nothing left to add and nothing to delete. It returns the whole chain, so this fills
        # the whole chain: the optional optics and the three device models included.
        interface = MockFiberPhotometryInterface(metadata_key="calcium_signal")
        metadata = interface.get_metadata_template()

        fiber_photometry_metadata = metadata["FiberPhotometry"]
        row_metadata = fiber_photometry_metadata["FiberPhotometryTable"]["rows"]["trace_0"]
        row_metadata["location"] = "VTA"
        row_metadata["excitation_wavelength_in_nm"] = 465.0
        row_metadata["emission_wavelength_in_nm"] = 525.0
        row_metadata["coordinates"] = (3.0, 1.0, 4.0)
        row_metadata["notes"] = "Recorded on the second day."
        row_metadata["dichroic_mirror_metadata_key"] = "dichroic_mirror"
        row_metadata["excitation_filter_metadata_key"] = "excitation_filter"
        row_metadata["emission_filter_metadata_key"] = "emission_filter"
        fiber_photometry_metadata["FiberPhotometryIndicators"]["indicator"].update(name="indicator", label="GCaMP6s")
        fiber_photometry_metadata["calcium_signal"]["description"] = "GCaMP6s at 465 nm in VTA."

        # The name of every entry is blank, so keeping one costs naming it.
        devices_metadata = metadata["Devices"]
        for device_metadata_key, device_metadata in devices_metadata.items():
            device_metadata["name"] = device_metadata_key
        for model_metadata_key, model_metadata in metadata["DeviceModels"].items():
            model_metadata["name"] = model_metadata_key

        devices_metadata["optical_fiber_0"]["fiber_insertion"] = dict(
            insertion_position_ap_in_mm=3.0,
            insertion_position_ml_in_mm=1.0,
            insertion_position_dv_in_mm=4.0,
            depth_in_mm=4.0,
        )
        devices_metadata["optical_fiber_0"]["device_model_metadata_key"] = "optical_fiber_model"
        devices_metadata["excitation_source"]["device_model_metadata_key"] = "excitation_source_model"
        devices_metadata["photodetector"]["device_model_metadata_key"] = "photodetector_model"
        for device_metadata_key in ("dichroic_mirror", "excitation_filter", "emission_filter"):
            devices_metadata[device_metadata_key].pop("device_model_metadata_key")

        device_models_metadata = metadata["DeviceModels"]
        device_models_metadata["optical_fiber_model"].update(manufacturer="Doric Lenses", numerical_aperture=0.48)
        device_models_metadata["excitation_source_model"].update(
            manufacturer="Doric Lenses", source_type="LED", excitation_mode="one-photon"
        )
        device_models_metadata["photodetector_model"].update(manufacturer="Doric Lenses", detector_type="photodiode")

        nwbfile_path = tmp_path / "filled_template.nwb"
        interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
        read_nwbfile = read_nwb(nwbfile_path)

        assert set(read_nwbfile.devices) == {
            "optical_fiber_0",
            "excitation_source",
            "photodetector",
            "dichroic_mirror",
            "excitation_filter",
            "emission_filter",
        }
        assert set(read_nwbfile.device_models) == {
            "optical_fiber_model",
            "excitation_source_model",
            "photodetector_model",
        }
        assert read_nwbfile.devices["optical_fiber_0"].model.numerical_aperture == 0.48

        table = read_nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
        assert len(table) == 1
        assert table["location"][0] == "VTA"
        assert table["notes"][0] == "Recorded on the second day."
        assert table["indicator"][0].label == "GCaMP6s"
        assert table["optical_fiber"][0].name == "optical_fiber_0"
        assert table["dichroic_mirror"][0].name == "dichroic_mirror"
        assert table["excitation_filter"][0].name == "excitation_filter"

        response_series = read_nwbfile.acquisition["FiberPhotometryResponseSeries"]
        assert response_series.description == "GCaMP6s at 465 nm in VTA."
        assert response_series.fiber_photometry_table_region.data[:] == [0]

    def test_minimally_annotated_metadata_round_trips(self, tmp_path):
        # The minimally annotated path: the default metadata describes only the response series, so the file
        # must contain exactly that and nothing fabricated — no table region, no devices, no lab metadata.
        interface = MockFiberPhotometryInterface()
        metadata = interface.get_metadata()

        nwbfile_path = tmp_path / "minimally_annotated.nwb"
        nwbfile = interface.create_nwbfile(metadata=metadata)
        with NWBHDF5IO(nwbfile_path, mode="w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(nwbfile_path, mode="r") as io:
            read_nwbfile = io.read()

            response_series = read_nwbfile.acquisition["FiberPhotometryResponseSeries"]
            assert response_series.name == "FiberPhotometryResponseSeries"
            # Nothing fabricated: no description was supplied, so it is written empty.
            assert response_series.description == ""
            assert response_series.unit == "a.u."
            assert response_series.data[:].shape == (100,)
            assert response_series.rate == pytest.approx(100.0)
            assert response_series.starting_time == 0.0

            assert response_series.fiber_photometry_table_region is None
            assert len(read_nwbfile.devices) == 0
            assert len(read_nwbfile.device_models) == 0
            assert "fiber_photometry" not in read_nwbfile.lab_meta_data

    def test_parent_container_processing_ophys_round_trips(self, tmp_path):
        # parent_container="processing/ophys" routes the series into the ophys processing module
        # instead of acquisition — verified through a full run_conversion / read_nwb cycle.
        interface = MockFiberPhotometryInterface()
        nwbfile_path = tmp_path / "processing_ophys.nwb"
        interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            parent_container="processing/ophys",
        )
        nwbfile = read_nwb(str(nwbfile_path))

        assert "FiberPhotometryResponseSeries" not in nwbfile.acquisition
        response_series = nwbfile.processing["ophys"]["FiberPhotometryResponseSeries"]
        assert response_series.unit == "a.u."
        assert response_series.data[:].shape == (100,)
        assert response_series.rate == pytest.approx(100.0)


class TestFiberPhotometryTemporalAlignment:
    """Gross temporal alignment: ``interface.alignment.shift_times`` places the interface on a session clock.

    The offset is rigid, so it moves the whole interface and changes nothing about its internal timing, and
    the source times are never mutated. Unlike the events interfaces, which hold the same component, this one
    also has a timestamps getter, so a shift is observable there as well as in the written file.

    The interface-wide offset is the only offset in the component, so it survives whatever the per-object
    operations do and applies on top of them. That is what the two composition tests pin, from either side.
    """

    def test_shift_moves_the_starting_time_and_accumulates(self):
        # Successive shifts add up, and the rate is untouched: a rigid translation cancels in the sample
        # differences calculate_regular_series_rate measures, so a shifted regular series stays regular.
        interface = MockFiberPhotometryInterface()
        interface.alignment.shift_times(1.0)
        interface.alignment.shift_times(0.5)

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(1.5)
        assert response_series.rate == pytest.approx(100.0)

    def test_shift_moves_an_explicitly_written_timestamps_vector(self):
        # The other timing representation. A regular series collapses to starting_time + rate, where the
        # shift lands in one scalar; forced onto the explicit vector, every sample of it has to move.
        interface = MockFiberPhotometryInterface()
        original_timestamps = interface.get_original_timestamps()
        interface.alignment.shift_times(2.5)

        nwbfile = interface.create_nwbfile(always_write_timestamps=True)
        response_series = nwbfile.acquisition["FiberPhotometryResponseSeries"]

        assert_array_equal(response_series.timestamps[:], original_timestamps + 2.5)

    def test_the_read_reports_the_accumulated_shift(self):
        # The decision this modality forced: a shift is visible through the read, since an interface that
        # reports its times should not report ones the file will disagree with. The source times stay where
        # they were, so the alignment is a transform and not an edit.
        interface = MockFiberPhotometryInterface()
        original_timestamps = interface.get_original_timestamps()
        interface.alignment.shift_times(3.0)

        assert_array_equal(interface.get_original_timestamps(), original_timestamps)
        assert_array_equal(interface.alignment[interface.metadata_key].get_times(), original_timestamps + 3.0)

    def test_set_times_writes_the_times_it_is_given(self):
        # Fine alignment by literal values, for per-sample times the user already trusts. Literal values
        # belong to one object, so this names the object they land on even though there is only one.
        interface = MockFiberPhotometryInterface()
        interface.alignment[interface.metadata_key].set_times(interface.get_original_timestamps() + 5.0)

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(5.0)
        assert response_series.rate == pytest.approx(100.0)

    def test_set_times_gives_the_times_the_file_carries_whatever_preceded_it(self):
        # set_times states the times outright, so a shift already applied is superseded for that object
        # rather than added on top of the values given. Reading them back returns them unchanged.
        interface = MockFiberPhotometryInterface()
        stated_times = interface.get_original_timestamps() + 5.0
        interface.alignment.shift_times(2.0)
        interface.alignment[interface.metadata_key].set_times(stated_times)

        assert_allclose(interface.alignment[interface.metadata_key].get_times(), stated_times)
        assert interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"].starting_time == pytest.approx(
            5.0
        )

    def test_a_shift_after_set_times_still_moves_the_object(self):
        # The other order. A shift is a correction applied to whatever the times are now, so it moves
        # stated times as readily as source ones, and the interface stays movable after a set.
        interface = MockFiberPhotometryInterface()
        interface.alignment[interface.metadata_key].set_times(interface.get_original_timestamps() + 5.0)
        interface.alignment.shift_times(2.0)

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(7.0)

    def test_remap_times_re_expresses_the_series_on_the_reference_clock(self):
        # Fine alignment against a reference clock. These pulses say the stream's clock runs at half the
        # reference's, so the series stretches: a 100 Hz recording is 50 Hz on the reference clock, and the
        # samples between pulses are interpolated rather than resampled.
        interface = MockFiberPhotometryInterface()
        interface.alignment.remap_times(local_sync_times=[0.0, 1.0], reference_sync_times=[10.0, 12.0])

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(10.0)
        assert response_series.rate == pytest.approx(50.0)

    def test_remap_times_builds_its_map_with_the_function_it_is_given(self):
        # The interpolation is a parameter, so a scheme numpy.interp cannot express (extrapolation, a
        # spline, identified pulses) is supplied rather than requested. The function here ignores the
        # pulses and states the map outright, which no default could produce.
        interface = MockFiberPhotometryInterface()
        interface.alignment.remap_times(
            local_sync_times=[0.0, 1.0],
            reference_sync_times=[10.0, 12.0],
            interpolation_function=lambda times, local, reference: times + 100.0,
        )

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(100.0)
        assert response_series.rate == pytest.approx(100.0)

    def test_remap_times_reads_the_pulses_on_the_times_the_interface_currently_reports(self):
        # The other side of the composition. Pulses are given in whatever frame the interface reports, which
        # a shift has already moved, so the remap consumes that frame rather than landing on top of it: the
        # same pulses on the reference clock put the series at ten seconds and not at thirteen.
        interface = MockFiberPhotometryInterface()
        interface.alignment.shift_times(3.0)
        interface.alignment.remap_times(local_sync_times=[3.0, 4.0], reference_sync_times=[10.0, 12.0])

        response_series = interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"]

        assert response_series.starting_time == pytest.approx(10.0)
        assert response_series.rate == pytest.approx(50.0)

    def test_the_interface_names_its_one_time_bearing_object(self):
        # The mapping surface. One response series means one key, the same one its metadata is under, and
        # reaching it gives the same operations scoped to that object.
        interface = MockFiberPhotometryInterface(metadata_key="my_series")

        assert interface.alignment.keys() == ("my_series",)
        interface.alignment["my_series"].set_times(interface.get_original_timestamps() + 2.0)
        assert interface.create_nwbfile().acquisition["FiberPhotometryResponseSeries"].starting_time == pytest.approx(
            2.0
        )

        with pytest.raises(KeyError, match="not a time-bearing object"):
            interface.alignment["nose"]

    @pytest.mark.parametrize(
        "legacy_call, new_call",
        [
            (
                lambda interface: interface.set_aligned_timestamps(
                    aligned_timestamps=interface.get_original_timestamps() + 5.0
                ),
                lambda interface: interface.alignment[interface.metadata_key].set_times(
                    interface.get_original_timestamps() + 5.0
                ),
            ),
            (
                lambda interface: interface.set_aligned_starting_time(aligned_starting_time=5.0),
                lambda interface: interface.alignment.shift_times(5.0),
            ),
            (
                lambda interface: interface.align_by_interpolation(
                    unaligned_timestamps=np.array([0.0, 1.0]), aligned_timestamps=np.array([5.0, 6.0])
                ),
                lambda interface: interface.alignment.remap_times(
                    local_sync_times=[0.0, 1.0], reference_sync_times=[5.0, 6.0]
                ),
            ),
        ],
    )
    def test_the_older_methods_warn_and_do_what_their_successor_does(self, legacy_call, new_call):
        # Each of the three writers has a successor now, so they route into it rather than holding a second
        # mechanism. Every one of these lands the series at five seconds by a different road.
        legacy_interface = MockFiberPhotometryInterface()
        with pytest.warns(FutureWarning, match="removed on or after August 2027"):
            legacy_call(legacy_interface)

        new_interface = MockFiberPhotometryInterface()
        new_call(new_interface)

        legacy_times = legacy_interface.alignment[legacy_interface.metadata_key].get_times()
        assert_allclose(legacy_times, new_interface.alignment[new_interface.metadata_key].get_times())
        assert legacy_times[0] == pytest.approx(5.0)

    def test_the_older_read_warns_and_returns_what_its_successor_returns(self):
        # The read is deprecated with the writers. An interface-level read has to assume the interface
        # writes one time-bearing object, which is the assumption the mapping surface exists to drop, so
        # its successor names the object rather than answering for the interface.
        interface = MockFiberPhotometryInterface()
        interface.alignment.shift_times(5.0)

        with pytest.warns(FutureWarning, match="removed on or after August 2027"):
            legacy_times = interface.get_timestamps()

        assert_array_equal(legacy_times, interface.alignment[interface.metadata_key].get_times())

    def test_shift_moves_the_commanded_voltage_series_with_the_response_series(self, full_metadata):
        # The second time-bearing object the writer produces, and the one place a shift has to be applied
        # by hand, since it reads its stream directly instead of going through get_timestamps. A shift is
        # interface-wide, so a commanded voltage left behind would misreport which samples it drove.
        # The mock has no dedicated commanded-voltage stream, so this points at a response stream: the
        # data is beside the point here, the timing is the subject.
        full_metadata["FiberPhotometry"]["CommandedVoltageSeries"] = dict(
            commanded_voltage=dict(
                name="CommandedVoltageSeries470",
                description="The voltage commanding the 470 nm excitation.",
                stream_name="470nm",
                index=0,
                unit="volts",
                frequency=211.0,
            )
        )
        interface = MockFiberPhotometryInterface(num_fibers=2)
        interface.alignment.shift_times(4.0)

        nwbfile = interface.create_nwbfile(metadata=full_metadata)

        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].starting_time == pytest.approx(4.0)
        assert nwbfile.acquisition["CommandedVoltageSeries470"].starting_time == pytest.approx(4.0)
