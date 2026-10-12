"""Unit tests for the DatasetInfo Pydantic model."""

from neuroconv.tools.nwb_helpers import ZarrBackendConfiguration


def test_zarr_backend_configuration_schema():
    assert ZarrBackendConfiguration.schema() is not None
    assert ZarrBackendConfiguration.schema_json() is not None
    assert ZarrBackendConfiguration.model_json_schema() is not None
