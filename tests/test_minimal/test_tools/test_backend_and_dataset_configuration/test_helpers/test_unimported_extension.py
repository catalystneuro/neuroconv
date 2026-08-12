"""Tests for writing an NWB file that was read from disk while an extension it uses was never imported."""

from pathlib import Path

import h5py
import numcodecs
import numpy as np
import pytest
from hdmf.build import BuildManager
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, TimeSeries, get_type_map, read_nwb
from pynwb.spec import NWBGroupSpec, NWBNamespaceBuilder
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, repack_nwbfile

NAMESPACE_NAME = "ndx-neuroconv-testing"
BACKEND_NWB_IO = {"hdf5": NWBHDF5IO, "zarr": NWBZarrIO}


def assert_written_with_default_compression(written_data):
    """Assert a written dataset carries the default compression of the backend it was written to."""
    if isinstance(written_data, h5py.Dataset):
        assert written_data.compression == "gzip"
    else:
        assert written_data.compressor == numcodecs.GZip(level=1)


@pytest.fixture
def extension_type_map(tmp_path):
    """
    A type map holding the namespace of an extension that this process has not imported.

    The namespace is registered in this local type map only, so the global type map stays ignorant of it, exactly as
    it is for a file written by another process using an installed extension that the reader never imports.
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

    return type_map


@pytest.fixture(params=["hdf5", "zarr"])
def unimported_extension_nwbfile_path(request, tmp_path, extension_type_map) -> Path:
    """Path to an NWB file, written in the parametrized backend, holding a container of the unimported extension."""
    source_backend = request.param
    extension_container_class = extension_type_map.get_dt_container_cls(
        namespace=NAMESPACE_NAME, data_type="ExtensionContainer"
    )

    nwbfile = mock_NWBFile()
    inner_series = TimeSeries(name="inner_series", data=np.arange(10, dtype="float64"), unit="a.u.", rate=1.0)
    nwbfile.add_acquisition(extension_container_class(name="extension_container", inner_series=inner_series))

    nwbfile_path = tmp_path / f"unimported_extension_{source_backend}.nwb"
    with BACKEND_NWB_IO[source_backend](str(nwbfile_path), mode="w", manager=BuildManager(extension_type_map)) as io:
        io.write(nwbfile)

    return nwbfile_path


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_and_write_nwbfile_with_unimported_extension(
    tmp_path, unimported_extension_nwbfile_path: Path, backend: str
):
    nwbfile = read_nwb(path=unimported_extension_nwbfile_path)

    export_path = tmp_path / f"exported_{backend}.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=export_path, backend=backend)
    nwbfile.read_io.close()

    with BACKEND_NWB_IO[backend](str(export_path), mode="r") as io:
        written_data = io.read().acquisition["extension_container"].inner_series.data
        np.testing.assert_array_equal(written_data[:], np.arange(10, dtype="float64"))
        assert_written_with_default_compression(written_data)


@pytest.mark.parametrize("export_backend", ["hdf5", "zarr", None])
def test_repack_nwbfile_with_unimported_extension(
    tmp_path, unimported_extension_nwbfile_path: Path, export_backend: str | None
):
    repacked_path = tmp_path / f"repacked_{export_backend}.nwb"
    repack_nwbfile(
        nwbfile_path=unimported_extension_nwbfile_path,
        export_nwbfile_path=repacked_path,
        export_backend=export_backend,
    )

    repacked_nwbfile = read_nwb(path=repacked_path)
    written_data = repacked_nwbfile.acquisition["extension_container"].inner_series.data
    np.testing.assert_array_equal(written_data[:], np.arange(10, dtype="float64"))
    assert_written_with_default_compression(written_data)
    repacked_nwbfile.read_io.close()
