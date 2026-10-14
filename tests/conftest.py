import pytest
import zarr
from packaging.version import Version


# TODO: remove with the zarr 3 port. Python 3.14 only installs zarr 3, and the Zarr backend still speaks zarr 2.
def pytest_collection_modifyitems(config, items):
    if Version(zarr.__version__).major < 3:
        return

    skip_zarr = pytest.mark.skip(reason="The Zarr backend does not support zarr 3 yet")
    for item in items:
        uses_zarr_fixture = any("zarr" in fixture_name for fixture_name in getattr(item, "fixturenames", ()))
        if "zarr" in item.nodeid.lower() or uses_zarr_fixture:
            item.add_marker(skip_zarr)
