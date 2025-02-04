"""Interface for converting single or multiple images to NWB format."""

from pathlib import Path
from typing import List, Literal, Optional

import numpy as np
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk
from PIL import Image
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage, RGBAImage, RGBImage

from ...basedatainterface import BaseDataInterface
from ...utils import DeepDict


class SingleImageIterator(AbstractDataChunkIterator):
    """Simple iterator to return a single image. This avoids loading the entire image into memory at initializing
    and instead loads it at writing time one by one"""

    def __init__(self, filename):
        self._filename = Path(filename)

        # Get image information without loading the full image
        with Image.open(self._filename) as img:
            self.image_mode = img.mode
            self._image_shape = img.size[::-1]  # PIL uses (width, height) instead of (height, width)
            self._max_shape = (None, None)

            self.number_of_bands = len(img.getbands())
            if self.number_of_bands > 1:
                self._image_shape += (self.number_of_bands,)
                self._max_shape += (self.number_of_bands,)

            # Calculate file size in bytes
            self._size_bytes = self._filename.stat().st_size
            # Calculate approximate memory size when loaded as numpy array
            self._memory_size = np.prod(self._image_shape) * np.dtype(float).itemsize

        self._images_returned = 0  # Number of images returned in __next__

    def __iter__(self):
        """Return the iterator object"""
        return self

    def __next__(self):
        """Return the DataChunk with the single full image"""
        if self._images_returned == 0:
            data = np.asarray(Image.open(self._filename))
            selection = (slice(None),) * data.ndim
            self._images_returned += 1
            return DataChunk(data=data, selection=selection)
        else:
            raise StopIteration

    def recommended_chunk_shape(self):
        """Recommend the chunk shape for the data array."""
        return self._image_shape

    def recommended_data_shape(self):
        """Recommend the initial shape for the data array."""
        return self._image_shape

    @property
    def dtype(self):
        """Define the data type of the array"""
        return np.dtype(float)

    @property
    def maxshape(self):
        """Property describing the maximum shape of the data array that is being iterated over"""
        return self._max_shape

    def __len__(self):
        return self._image_shape[0]

    @property
    def size_info(self):
        """Return dictionary with size information"""
        return {
            "file_size_bytes": self._size_bytes,
            "memory_size_bytes": self._memory_size,
            "shape": self._image_shape,
            "mode": self.image_mode,
            "bands": self.number_of_bands,
        }


class ImageInterface(BaseDataInterface):
    """Interface for converting single or multiple images to NWB format."""

    display_name = "Image Interface"
    keywords = ("image",)
    associated_suffixes = (".png", ".jpg", ".jpeg", ".tiff", ".tif")
    info = "Interface for converting single or multiple images to NWB format."

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the schema for the source_data."""
        return dict(
            required=["file_paths"],
            properties=dict(
                file_paths=dict(
                    type=["array", "string"],
                    items=dict(type="string"),
                    description="Path(s) to image file(s) to be converted",
                ),
                folder_path=dict(
                    type="string",
                    description="Path to folder containing images to be converted. Used if file_paths not provided.",
                ),
            ),
        )

    def __init__(
        self,
        file_paths: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        images_location: Literal["acquisition", "stimulus"] = "acquisition",
        verbose: bool = True,
    ):
        """
        Initialize the ImageInterface.

        Parameters
        ----------
        file_paths : str or list of str, optional
            Path(s) to image file(s) to be converted
        folder_path : str, optional
            Path to folder containing images to be converted. Used if file_paths not provided.
        verbose : bool, default: True
            Whether to print status messages
        """
        if file_paths is None and folder_path is None:
            raise ValueError("Either file_paths or folder_path must be provided")

        if file_paths is not None and folder_path is not None:
            raise ValueError("Only one of file_paths or folder_path should be provided")

        if isinstance(file_paths, str):
            file_paths = [file_paths]

        self.file_paths = file_paths
        self.folder_path = folder_path
        self.images_location = images_location

        super().__init__(
            verbose=verbose, file_paths=file_paths, folder_path=folder_path, images_location=images_location
        )

        # Process paths
        if folder_path is not None:
            folder = Path(folder_path)
            if not folder.exists():
                raise ValueError(f"Folder {folder} does not exist")

            # Get all image files in folder
            file_paths = []
            for suffix in self.associated_suffixes:
                file_paths.extend(folder.glob(f"*{suffix}"))

            if not file_paths:
                raise ValueError(f"No image files found in {folder}")

            self.file_paths = [str(p) for p in file_paths]
        else:
            self.file_paths = [str(Path(p).absolute()) for p in file_paths]

            # Validate paths
            for path in self.file_paths:
                if not Path(path).exists():
                    raise ValueError(f"File {path} does not exist")

    def get_metadata(self) -> DeepDict:
        """Get metadata for the images."""
        metadata = super().get_metadata()

        # Add basic metadata about the images
        metadata["Images"] = dict(description="Images loaded through ImageInterface", num_images=len(self.file_paths))

        return metadata

    def _get_image_container_type(self, image_path: str) -> Literal["GrayscaleImage", "RGBImage", "RGBAImage"]:
        """Determine the appropriate image container type based on the image mode."""
        with Image.open(image_path) as img:
            mode = img.mode

        if mode == "L":
            return "GrayscaleImage"
        elif mode == "RGB":
            return "RGBImage"
        elif mode == "RGBA":
            return "RGBAImage"
        else:
            raise ValueError(f"Unsupported image mode: {mode}")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        container_name: str = "images",
    ) -> None:
        """
        Add the image data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the images to
        metadata : dict, optional
            Metadata for the images
        container_name : str, default: "images"
            Name of the Images container
        """
        if metadata is None:
            metadata = self.get_metadata()

        # Create Images container
        images_container = Images(
            name=container_name,
            description=metadata.get("Images", {}).get("description", "Images loaded through ImageInterface"),
        )

        # Process each image
        for file_path in self.file_paths:
            # Create iterator for memory-efficient loading
            iterator = SingleImageIterator(file_path)

            # Get image name from file name
            image_name = Path(file_path).stem

            # Determine image type and create appropriate container
            container_type = self._get_image_container_type(file_path)
            image_class = {"GrayscaleImage": GrayscaleImage, "RGBImage": RGBImage, "RGBAImage": RGBAImage}[
                container_type
            ]

            # Create image container with iterator
            image_container = image_class(name=image_name, data=iterator)

            # Add to images container
            images_container.add_image(image_container)

        # Add images container to file
        if self.images_location == "acquisition":
            nwbfile.add_acquisition(images_container)
        else:
            nwbfile.add_stimulus(images_container)
