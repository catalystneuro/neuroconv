"""Helper functions for performing more complicated import operations."""
import importlib
from typing import Optional


def safe_import(module_name: str, pypi_package_name: Optional[str] = None):
    """Import a module if it is installed or raise a more informative installation error if not."""
    try:
        return importlib.import_module(name=module_name)
    except ModuleNotFoundError:
        pypi_package_display_name = pypi_package_name or module_name
        raise ModuleNotFoundError(
            f"\nThe attempt to import '{module_name}' failed!\n"
            f"To install this package, please run\n\n\tpip install {pypi_package_display_name}\n"
        )
