import pytest

from neuroconv.tools.importing import is_package_installed


# hdmf_zarr installs only on Python 3.12 and newer, and the Zarr backend requires it.
def pytest_collection_modifyitems(config, items):
    if is_package_installed(package_name="hdmf_zarr"):
        return

    skip_zarr = pytest.mark.skip(reason="The Zarr backend requires hdmf_zarr")
    for item in items:
        uses_zarr_fixture = any("zarr" in fixture_name for fixture_name in getattr(item, "fixturenames", ()))
        if "zarr" in item.nodeid.lower() or uses_zarr_fixture:
            item.add_marker(skip_zarr)
