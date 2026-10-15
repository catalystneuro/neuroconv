import pytest
import zarr
from packaging.version import Version


# Python 3.13 and older resolve zarr 2, and the Zarr backend requires zarr 3.
def pytest_collection_modifyitems(config, items):
    if Version(zarr.__version__).major >= 3:
        return

    skip_zarr = pytest.mark.skip(reason="The Zarr backend requires zarr 3")
    for item in items:
        uses_zarr_fixture = any("zarr" in fixture_name for fixture_name in getattr(item, "fixturenames", ()))
        if "zarr" in item.nodeid.lower() or uses_zarr_fixture:
            item.add_marker(skip_zarr)
