from pathlib import Path
from typing import Optional, TypeVar, Union

import numpy as np

FilePath = TypeVar("FilePathType", str, Path)
DirectoryPath = TypeVar("FolderPathType", str, Path)
OptionalFilePathType = Optional[FilePath]
OptionalFolderPathType = Optional[DirectoryPath]
ArrayType = Union[list, np.ndarray]
OptionalArrayType = Optional[ArrayType]
FloatType = float
IntType = Union[int, np.integer]
