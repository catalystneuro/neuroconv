from pathlib import Path
from typing import Optional, TypeVar, Union

import numpy as np

FilePathType = TypeVar("FilePathType", str, Path)
FolderPathType = TypeVar("FolderPathType", str, Path)
OptionalFilePathType = Optional[FilePathType]
OptionalFolderPathType = Optional[FolderPathType]
ArrayType = Union[list, np.ndarray]
OptionalArrayType = Optional[ArrayType]
FloatType = float
IntType = Union[int, np.integer]
