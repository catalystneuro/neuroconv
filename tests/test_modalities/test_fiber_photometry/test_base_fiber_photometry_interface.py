"""Data-free tests of the shared fiber photometry writer, driven by ``MockFiberPhotometryInterface``."""

import re
from datetime import datetime, timezone

import numpy as np
import pytest
from jsonschema.validators import Draft7Validator
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockFiberPhotometryInterface

# The ``full_metadata`` fixture describes two fibers at one excitation wavelength, so the interfaces
# it is written against need two single-fiber source stores rather than the single-store default.
TWO_FIBER_STREAMS = ("store_0", "store_1")


@pytest.fixture
def full_metadata():
    """A complete, hand-built fiber photometry metadata chain for the default mock interface.

    Test data (not a public API): device models, devices, an indicator, a two-row ``FiberPhotometryTable``,
    and the response-series region — the full provenance a user would supply to write everything.
    """
    interface = MockFiberPhotometryInterface(stream_names=TWO_FIBER_STREAMS)
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
    interface_kwargs = dict(stream_names=TWO_FIBER_STREAMS)
    conversion_options = dict(stub_test=True, stub_samples=3)

    # Hand-supplied, not read back from the interface: the mock's two seeded standard-normal traces.
    expected_response_series_data = np.array(
        [
            [0.1257302210933933, 0.345584192064786],
            [-0.1321048632913019, 0.8216181435011584],
            [0.6404226504432821, 0.33043707618338714],
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

    def test_channel_order_follows_stream_names(self):
        # Which channel a stream lands on is positional: np.concatenate(axis=1) preserves stream_names
        # order, and nothing downstream re-derives it, so the table region has to line up by position.
        interface = MockFiberPhotometryInterface(stream_names=["first", "second", "third"])
        data = interface._read_response_data()

        assert data.shape == (100, 3)
        for index, stream_name in enumerate(interface.stream_names):
            assert_array_equal(data[:, index], interface._get_stream_data(stream_name=stream_name))

    def test_multi_fiber_stream_contributes_one_column_per_fiber(self):
        # A single stream can itself be multi-fiber (one acquisition store holding several fibers),
        # in which case _get_stream_data returns 2-D and skips the np.newaxis promotion entirely.
        interface = MockFiberPhotometryInterface(stream_names="fibers", fibers_per_stream=4)
        stream_data = interface._get_stream_data(stream_name="fibers")
        assert stream_data.ndim == 2

        data = interface._read_response_data()
        assert data.shape == (100, 4)
        assert_array_equal(data, stream_data)

    def test_mixed_fiber_counts_stack_by_total_fibers(self):
        # A 3-fiber store stacked with a single-fiber one: columns total the per-stream fiber counts,
        # not the stream count, and the promoted 1-D stream stacks alongside the 2-D one.
        interface = MockFiberPhotometryInterface(stream_names=["fiber_array", "lone_fiber"], fibers_per_stream=[3, 1])
        data = interface._read_response_data()

        assert data.shape == (100, 4)
        assert_array_equal(data[:, :3], interface._get_stream_data(stream_name="fiber_array"))
        assert_array_equal(data[:, 3], interface._get_stream_data(stream_name="lone_fiber"))

    def test_fibers_per_stream_length_mismatch_errors(self):
        expected_error = "fibers_per_stream has 3 entries but there are 2 stream(s)"
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            MockFiberPhotometryInterface(stream_names=["a", "b"], fibers_per_stream=[1, 2, 3])

    def test_single_stream_collapses_to_one_column(self):
        # A lone column is written as a 1-D series rather than an (N, 1) one.
        interface = MockFiberPhotometryInterface(stream_names="store_0")
        nwbfile = interface.create_nwbfile()

        assert nwbfile.acquisition["FiberPhotometryResponseSeries"].data[:].shape == (100,)

    def test_fully_annotated_metadata_round_trips(self, tmp_path, full_metadata):
        # The fully annotated path: a complete provenance chain is supplied, and every piece of it must
        # survive a write/read cycle — device models, devices (with model links and fiber insertion), the
        # indicator, both table rows in full, the region, and the response series.
        interface = MockFiberPhotometryInterface(stream_names=TWO_FIBER_STREAMS)

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

        interface = MockFiberPhotometryInterface(stream_names=TWO_FIBER_STREAMS)
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

        nwbfile = MockFiberPhotometryInterface(stream_names=TWO_FIBER_STREAMS).create_nwbfile(metadata=full_metadata)

        assert "Camera1" not in nwbfile.devices
        assert "camera_model" not in nwbfile.device_models
        assert "optical_fiber_dms" in nwbfile.devices
        assert "optical_fiber_model" in nwbfile.device_models

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
