import sys
import importlib.util
from platform import python_version
from packaging import version
from types import ModuleType
from typing import Optional, Dict, List


HAVE_SONPY = True
try:
    import sonpy
except ImportError:
    HAVE_SONPY = False
INSTALL_MESSAGE = "Please install sonpy to use this interface (pip install sonpy)!"
if sys.platform == "darwin" and version.parse(python_version()) < version.parse("3.8"):
    HAVE_SONPY = False
    INSTALL_MESSAGE = "The sonpy package (CED dependency) is not available on Mac for Python versions below 3.8!"


def get_package(
    package_name: str,
    installation_source: str = "pip",
    package_installation_display: Optional[str] = None,
    excluded_platforms_and_python_versions: Optional[Dict[str, List[str]]] = None,
) -> ModuleType:
    """
    Check if package is installed and return module if so.

    Otherwise, raise informative error describing how to perform the installation.
    Inspired by https://docs.python.org/3/library/importlib.html#checking-if-a-module-can-be-imported.

    Parameters
    ----------
    name : str
        Name of the package to be installed.

    Raises
    ------
    ModuleNotFoundError
    """
    package_installation_display = package_installation_display or package_name
    excluded_platforms_and_python_versions = excluded_platforms_and_python_versions or dict()

    if package_name in sys.modules:
        return sys.modules[package_name]

    if importlib.util.find_spec(package_name) is not None:
        return importlib.import_module(name=package_name)

    for excluded_versions in excluded_platforms_and_python_versions.get(sys.platform, list()):
        if version.parse(python_version()) < version.parse(excluded_versions):
            raise ModuleNotFoundError(
                f"\nThe package {package_installation_display} is not available on the {sys.platform} platform for "
                f"Python versions {excluded_platforms_and_python_versions[sys.platform]}!"
            )

    raise ModuleNotFoundError(
        f"\nThe required package'{package_name}' is not installed!\n"
        f"To install this package, please run\n\n\t{installation_source} install {package_installation_display}\n"
    )
