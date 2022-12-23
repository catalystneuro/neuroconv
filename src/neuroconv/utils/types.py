"""Authors: Luiz Tauffer, Cody Baker, Saksham Sharda and Ben Dichter."""
from pathlib import Path
from typing import Optional, Union
from typing import TypeVar

import numpy as np
from pydantic import FilePath, DirectoryPath

FilePathType = FilePath
FolderPathType = DirectoryPath
