"""Tests for writing an NWB file that was read from disk while an extension it uses was never imported."""

import numpy as np
import pytest
from hdmf.build import BuildManager
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, TimeSeries, get_type_map, read_nwb
from pynwb.spec import NWBAttributeSpec, NWBDatasetSpec, NWBGroupSpec, NWBNamespaceBuilder
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

NAMESPACE_NAME = "ndx-neuroconv-testing"


@pytest.fixture
def unimported_extension_nwbfile_path(tmp_path) -> str:
    """
    Path to an NWB file holding a container from an extension that this process has not imported.

    The extension namespace is registered in a local type map used only to write the file, so the global type map
    stays ignorant of it, exactly as it would be for a file written by another process using an installed extension
    that the reader never imports.
    """
    namespace_builder = NWBNamespaceBuilder(
        name=NAMESPACE_NAME,
        version="0.1.0",
        doc="Namespace of an extension used to write a test file.",
        author=["CatalystNeuro"],
        contact=["conversions@catalystneuro.com"],
    )
    namespace_builder.include_type("NWBDataInterface", namespace="core")
    namespace_builder.include_type("TimeSeries", namespace="core")
    namespace_builder.add_spec(
        source=f"{NAMESPACE_NAME}.extensions.yaml",
        spec=NWBGroupSpec(
            neurodata_type_def="ExtensionContainer",
            neurodata_type_inc="NWBDataInterface",
            doc="A container defined by an extension, holding a time series.",
            groups=[NWBGroupSpec(name="inner_series", neurodata_type_inc="TimeSeries", doc="An inner time series.")],
        ),
    )
    namespace_builder.export(path=f"{NAMESPACE_NAME}.namespace.yaml", outdir=str(tmp_path))

    type_map = get_type_map()  # A deep copy of the global type map
    type_map.load_namespaces(str(tmp_path / f"{NAMESPACE_NAME}.namespace.yaml"))
    extension_container_class = type_map.get_dt_container_cls(namespace=NAMESPACE_NAME, data_type="ExtensionContainer")

    nwbfile = mock_NWBFile()
    inner_series = TimeSeries(name="inner_series", data=np.arange(10, dtype="float64"), unit="a.u.", rate=1.0)
    nwbfile.add_acquisition(extension_container_class(name="extension_container", inner_series=inner_series))

    nwbfile_path = tmp_path / "unimported_extension.nwb"
    with NWBHDF5IO(str(nwbfile_path), mode="w", manager=BuildManager(type_map)) as io:
        io.write(nwbfile)

    return str(nwbfile_path)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_and_write_nwbfile_with_unimported_extension(
    tmp_path, unimported_extension_nwbfile_path: str, backend: str
):
    nwbfile = read_nwb(path=unimported_extension_nwbfile_path)

    export_path = str(tmp_path / f"exported_{backend}.nwb")
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=export_path, backend=backend)
    nwbfile.read_io.close()

    io_class = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with io_class(export_path, mode="r") as io:
        written_nwbfile = io.read()
        written_data = written_nwbfile.acquisition["extension_container"].inner_series.data
        np.testing.assert_array_equal(written_data[:], np.arange(10, dtype="float64"))
        if backend == "hdf5":
            assert written_data.compression == "gzip"
        else:
            from zarr.codecs import GzipCodec

            assert written_data.compressors == (GzipCodec(level=4),)


@pytest.fixture
def legacy_ndx_events_nwbfile_path(tmp_path) -> str:
    """
    Path to an NWB file holding an ndx-events 0.2 `Events` container, written without ndx-events installed.

    The namespace reproduces the name and the `Events` layout of ndx-events 0.2, so reading the file back builds
    `Events` from the cached spec, as it is for every reader that does not import the installed ndx-events classes.
    A regular `TimeSeries` sits beside it to show the rest of the file is still configured.
    """
    namespace_builder = NWBNamespaceBuilder(
        name="ndx-events",
        version="0.2.0",
        doc="The ndx-events 0.2 `Events` type, reproduced to write a test file.",
        author=["CatalystNeuro"],
        contact=["conversions@catalystneuro.com"],
    )
    namespace_builder.include_type("NWBDataInterface", namespace="core")
    namespace_builder.add_spec(
        source="ndx-events.extensions.yaml",
        spec=NWBGroupSpec(
            neurodata_type_def="Events",
            neurodata_type_inc="NWBDataInterface",
            doc="A list of timestamps, stored in seconds, of an event.",
            attributes=[NWBAttributeSpec(name="description", dtype="text", doc="Description of the event.")],
            datasets=[
                NWBDatasetSpec(
                    name="timestamps",
                    dtype="float32",
                    dims=["num_events"],
                    shape=[None],
                    doc="Event timestamps, in seconds.",
                )
            ],
        ),
    )
    namespace_builder.export(path="ndx-events.namespace.yaml", outdir=str(tmp_path))

    type_map = get_type_map()  # A deep copy of the global type map
    type_map.load_namespaces(str(tmp_path / "ndx-events.namespace.yaml"))
    events_class = type_map.get_dt_container_cls(namespace="ndx-events", data_type="Events")

    nwbfile = mock_NWBFile()
    timestamps = np.array([0.5, 1.5, 2.5], dtype="float32")
    nwbfile.add_acquisition(events_class(name="reward_times", description="Reward times.", timestamps=timestamps))
    nwbfile.add_acquisition(TimeSeries(name="trace", data=np.arange(10, dtype="float64"), unit="a.u.", rate=1.0))

    nwbfile_path = tmp_path / "legacy_ndx_events.nwb"
    with NWBHDF5IO(str(nwbfile_path), mode="w", manager=BuildManager(type_map)) as io:
        io.write(nwbfile)

    return str(nwbfile_path)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_and_write_nwbfile_with_legacy_ndx_events(
    tmp_path, legacy_ndx_events_nwbfile_path: str, backend: str
):
    nwbfile = read_nwb(path=legacy_ndx_events_nwbfile_path)

    export_path = str(tmp_path / f"exported_{backend}.nwb")
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=export_path, backend=backend)
    nwbfile.read_io.close()

    io_class = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with io_class(export_path, mode="r") as io:
        written_nwbfile = io.read()
        written_timestamps = written_nwbfile.acquisition["reward_times"].timestamps
        np.testing.assert_array_equal(written_timestamps[:], np.array([0.5, 1.5, 2.5], dtype="float32"))
        written_data = written_nwbfile.acquisition["trace"].data
        np.testing.assert_array_equal(written_data[:], np.arange(10, dtype="float64"))
        if backend == "hdf5":
            assert written_data.compression == "gzip"
        else:
            from zarr.codecs import GzipCodec

            assert written_data.compressors == (GzipCodec(level=4),)
