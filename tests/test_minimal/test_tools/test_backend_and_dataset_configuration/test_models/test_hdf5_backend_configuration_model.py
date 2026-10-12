"""Unit tests for the DatasetInfo Pydantic model."""

from neuroconv.tools.nwb_helpers import HDF5BackendConfiguration


def test_hdf5_backend_configuration_schema():
    assert HDF5BackendConfiguration.schema() is not None
    assert HDF5BackendConfiguration.schema_json() is not None
    assert HDF5BackendConfiguration.model_json_schema() is not None
