"""Tool functions for performaing imports."""
import sys
import importlib.util
from platform import python_version
from types import ModuleType
from typing import Optional, Dict, List

from packaging import version


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
    package_name : str
        Name of the package to be imported.
    installation_source : str, optional
        Name of the installation source of the package.
        Typically either "pip" or "conda".
        Defaults to "pip".
    package_installation_display : str, optional
        Name of the package to be installed via the 'installation_source', in case it differs from the import name.
        Defaults to 'package_name'.
    excluded_platforms_and_python_versions : dict mapping string platform names to a list of string versions, optional
        In case some combinations of platforms or Python versions are not allowed for the given package, specify
        this dictionary to raise a more specific error to that issue.
        For example, `excluded_platforms_and_python_versions = dict(darwin=["3.7"])` will raise an informative error
        when running on MacOS with Python version 3.7.
        Allows all platforms and Python versions used by default.

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

    for excluded_version in excluded_platforms_and_python_versions.get(sys.platform, list()):
        if version.parse(python_version()).minor == version.parse(excluded_version).minor:
            raise ModuleNotFoundError(
                f"\nThe package '{package_installation_display}' is not available on the {sys.platform} platform for "
                f"Python version {excluded_version}!"
            )

    raise ModuleNotFoundError(
        f"\nThe required package'{package_name}' is not installed!\n"
        f"To install this package, please run\n\n\t{installation_source} install {package_installation_display}\n"
    )
