from typing import Optional, Union

import numpy as np

# from typing_extensions import Annotated


# def nd_array_custom_before_validator(object_: Union[list, np.ndarray]):
#    if isinstance(object_, list):
#        return np.array(object_)
#    return object_


# ArrayType = Annotated[Union[list, np.ndarray], BeforeValidator(nd_array_custom_before_validator)]
ArrayType = Union[list, np.ndarray]
OptionalArrayType = Optional[ArrayType]
FloatType = float
IntType = Union[int, np.integer]


# TODO: remove after 3/1/2025
def __getattr__(name):
    from typing import Optional
    from warnings import warn

    from pydantic import DirectoryPath, FilePath

    if name == "FilePathType":
        message = (
            "The 'FilePathType' type has been deprecated and will be removed after 3/1/2025. "
            "Please use `pydantic.FilePath` instead."
        )
        warn(message=message, category=DeprecationWarning, stacklevel=2)

        return FilePath
    if name == "OptionalFilePathType":
        message = (
            "The 'OptionalFilePathType' type has been deprecated and will be removed after 3/1/2025. "
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
