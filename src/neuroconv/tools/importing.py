"""Tool functions for performing imports."""
import importlib.util
import sys
from platform import processor, python_version
from types import ModuleType
from typing import Dict, List, Optional, Union

from packaging import version


def get_package(
    package_name: str,
    installation_instructions: Optional[str] = None,
    excluded_python_versions: Optional[List[str]] = None,
    excluded_platforms_and_python_versions: Optional[Dict[str, Union[List[str], Dict[str, List[str]]]]] = None,
) -> ModuleType:
    """
    Check if package is installed and return module if so.

    Otherwise, raise informative error describing how to perform the installation.
    Inspired by https://docs.python.org/3/library/importlib.html#checking-if-a-module-can-be-imported.

    Parameters
    ----------
    package_name : str
        Name of the package to be imported.
    installation_instructions : str, optional
        String describing the source, options, and alias of package name (if needed) for installation.
        For example,
            >>> installation_source = "conda install -c conda-forge my-package-name"
        Defaults to f"pip install {package_name}".
    excluded_python_versions : list of strs, optional
        If a given package has no distribution available for a certain Python version, it can be excluded by this
        import across all platforms. If you wish to be more specific about combinations of platforms and versions,
        use the 'excluded_platforms_and_python_versions' keyword argument instead.
        Allows all Python versions by default.
    excluded_platforms_and_python_versions : dict, optional
        Mapping of string platform names to a list of string versions.
        Valid platform strings are: ["linux", "win32", "darwin"] or any other variant used by sys.platform

        In case some combinations of platforms or Python versions are not allowed for the given package,
        specify this dictionary to raise a more specific error to that issue.

        For example, `excluded_platforms_and_python_versions = dict(darwin=["3.7"])` will raise an
        informative error when running on MacOS with Python version 3.7.

        This also applies to specific architectures of platforms, such as
        `excluded_platforms_and_python_versions = dict(darwin=dict(arm=["3.7"]))` to exclude a specific Python
        version for M1 Macs.

        Allows all platforms and Python versions by default.

    Raises
    ------
    ModuleNotFoundError
    """
    installation_instructions = installation_instructions or f"pip install {package_name}"
    excluded_python_versions = excluded_python_versions or list()
    excluded_platforms_and_python_versions = excluded_platforms_and_python_versions or dict()

    python_minor_version = version.parse(python_version()).minor
    excluded_python_minor_versions = [
        version.parse(excluded_version).minor for excluded_version in excluded_python_versions
    ]
    if python_minor_version in excluded_python_minor_versions:
        raise ModuleNotFoundError(
            f"\nThe package '{package_name}' is not available for Python version 3.{python_minor_version}!"
        )

    # Specific architecture of specific platform is specified
    if isinstance(excluded_platforms_and_python_versions.get(sys.platform), dict):
        architecture = processor()
        for excluded_version in excluded_platforms_and_python_versions[sys.platform].get(architecture, list()):
            platform_string = f"{sys.platform}:{architecture}"

            if python_minor_version == version.parse(excluded_version).minor:
                raise ModuleNotFoundError(
                    f"\nThe package '{package_name}' is not available on the {platform_string} platform for "
                    f"Python version {excluded_version}!"
                )
    else:
        for excluded_version in excluded_platforms_and_python_versions.get(sys.platform, list()):
            if python_minor_version == version.parse(excluded_version).minor:
                raise ModuleNotFoundError(
                    f"\nThe package '{package_name}' is not available on the {sys.platform} platform for "
                    f"Python version {excluded_version}!"
                )

    if package_name in sys.modules:
        return sys.modules[package_name]

    if importlib.util.find_spec(package_name) is not None:
        return importlib.import_module(name=package_name)

    raise ModuleNotFoundError(
        f"\nThe required package'{package_name}' is not installed!\n"
        f"To install this package, please run\n\n\t{installation_instructions}\n"
    )
