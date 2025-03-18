from .checks import calculate_regular_series_rate
from .dict import (
    DeepDict,
    append_replace_dict_in_list,
    dict_deep_update,
    exist_dict_in_list,
    load_dict_from_file,
)
from .json_schema import (
    NWBMetaDataEncoder,
    fill_defaults,
    get_base_schema,
    get_metadata_schema_for_icephys,
    get_schema_from_hdmf_class,
    get_json_schema_from_method_signature,
    unroot_schema,
    get_json_schema_from_method_signature,
)
from .types import (
    ArrayType,
    IntType,
    OptionalArrayType,
)


# TODO: remove after 3/1/2025
def __getattr__(name):
    from warnings import warn
    from typing import Optional

    from pydantic import FilePath, DirectoryPath

    if name == "FilePath":
        message = (
            "The 'FilePath' type has been deprecated and will be removed after 3/1/2025. "
            "Please use `pydantic.FilePath` instead."
        )
        warn(message=message, category=DeprecationWarning, stacklevel=2)

        return FilePath
    if name == "OptionalFilePath":
        message = (
            "The 'OptionalFilePath' type has been deprecated and will be removed after 3/1/2025. "
            "Please use `typing.Optional[pydantic.FilePath]` instead."
        )
        warn(message=message, category=DeprecationWarning, stacklevel=2)

        return Optional[FilePath]
    if name == "FolderPathType":
        message = (
            "The 'FolderPathType' type has been deprecated and will be removed after 3/1/2025. "
            "Please use `pydantic.DirectoryPath` instead."
        )
        warn(message=message, category=DeprecationWarning, stacklevel=2)

        return DirectoryPath
    if name == "OptionalFolderPathType":
        message = (
            "The 'OptionalFolderPathType' type has been deprecated and will be removed after 3/1/2025. "
            "Please use `typing.Optional[pydantic.DirectoryPath]` instead."
        )
        warn(message=message, category=DeprecationWarning, stacklevel=2)

        return Optional[DirectoryPath]
