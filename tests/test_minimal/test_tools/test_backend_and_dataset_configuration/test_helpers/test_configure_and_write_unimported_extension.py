"""Tests for writing an NWB file that was read from disk while an extension it uses was never imported."""

import numpy as np
import pytest
from hdmf.build import BuildManager
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, TimeSeries, get_type_map, read_nwb
from pynwb.spec import NWBDatasetSpec, NWBGroupSpec, NWBNamespaceBuilder
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
def unimported_extension_datasets_nwbfile_path(tmp_path) -> str:
    """
    Path to an NWB file holding an extension container that is not a `TimeSeries` but has `data` and `timestamps`.

    The container is written with a local type map, so reading the file back builds its class from the cached spec.
    """
    namespace_builder = NWBNamespaceBuilder(
        name=NAMESPACE_NAME,
        version="0.1.0",
        doc="Namespace of an extension used to write a test file.",
        author=["CatalystNeuro"],
        contact=["conversions@catalystneuro.com"],
    )
    namespace_builder.include_type("NWBDataInterface", namespace="core")
    namespace_builder.add_spec(
        source=f"{NAMESPACE_NAME}.extensions.yaml",
        spec=NWBGroupSpec(
            neurodata_type_def="ExtensionRecording",
            neurodata_type_inc="NWBDataInterface",
            doc="A container defined by an extension, holding its own data and timestamps.",
            datasets=[
                NWBDatasetSpec(name="data", dtype="float64", dims=["num_samples"], shape=[None], doc="The data."),
                NWBDatasetSpec(
                    name="timestamps", dtype="float64", dims=["num_samples"], shape=[None], doc="The timestamps."
                ),
            ],
        ),
    )
    namespace_builder.export(path=f"{NAMESPACE_NAME}.namespace.yaml", outdir=str(tmp_path))

    type_map = get_type_map()  # A deep copy of the global type map
    type_map.load_namespaces(str(tmp_path / f"{NAMESPACE_NAME}.namespace.yaml"))
    extension_recording_class = type_map.get_dt_container_cls(namespace=NAMESPACE_NAME, data_type="ExtensionRecording")

    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(
        extension_recording_class(
            name="extension_recording",
            data=np.arange(10, dtype="float64"),
            timestamps=np.arange(10, dtype="float64") / 10.0,
        )
    )

    nwbfile_path = tmp_path / "unimported_extension_datasets.nwb"
    with NWBHDF5IO(str(nwbfile_path), mode="w", manager=BuildManager(type_map)) as io:
        io.write(nwbfile)

    return str(nwbfile_path)


@pytest.mark.parametrize("backend", ["hdf5", "zarr"])
def test_configure_and_write_nwbfile_with_unimported_extension_datasets(
    tmp_path, unimported_extension_datasets_nwbfile_path: str, backend: str
):
    nwbfile = read_nwb(path=unimported_extension_datasets_nwbfile_path)

    export_path = str(tmp_path / f"exported_{backend}.nwb")
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=export_path, backend=backend)
    nwbfile.read_io.close()

    io_class = NWBHDF5IO if backend == "hdf5" else NWBZarrIO
    with io_class(export_path, mode="r") as io:
        written_nwbfile = io.read()
        written_recording = written_nwbfile.acquisition["extension_recording"]
        np.testing.assert_array_equal(written_recording.data[:], np.arange(10, dtype="float64"))
        np.testing.assert_array_equal(
            written_recording.timestamps[:],
            np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]),
        )
        if backend == "hdf5":
            assert written_recording.data.compression == "gzip"
            assert written_recording.timestamps.compression == "gzip"
        else:
            from zarr.codecs import GzipCodec
            from zarr.codecs.numcodecs import Shuffle

            assert written_recording.data.compressors == (GzipCodec(level=4),)
            assert written_recording.timestamps.compressors == (Shuffle(elementsize=8), GzipCodec(level=4))
