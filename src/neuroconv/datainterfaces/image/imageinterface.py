"""Interface for converting single or multiple images to NWB format."""

import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage, RGBAImage, RGBImage

from ...basedatainterface import BaseDataInterface
from ...utils import DeepDict


class SingleImageIterator(AbstractDataChunkIterator):
    """Simple iterator to return a single image. This avoids loading the entire image into memory at initializing
    and instead loads it at writing time one by one"""

    def __init__(self, file_path: str | Path):
        self._file_path = Path(file_path)
        from PIL import Image

        # Get image information without loading the full image
        with Image.open(self._file_path) as img:
            self.image_mode = img.mode
            self._image_shape = img.size[::-1]  # PIL uses (width, height) instead of (height, width)
            self._max_shape = (None, None)

            self.number_of_bands = len(img.getbands())
            if self.number_of_bands > 1:
                self._image_shape += (self.number_of_bands,)
                self._max_shape += (self.number_of_bands,)

            # For LA mode, adjust shape to RGBA
            if self.image_mode == "LA":
                self._image_shape = self._image_shape[:-1] + (4,)
                self._max_shape = self._max_shape[:-1] + (4,)

            # Calculate file size in bytes
            self._size_bytes = self._file_path.stat().st_size
            # Calculate approximate memory size when loaded as numpy array
            self._memory_size = np.prod(self._image_shape) * np.dtype(float).itemsize

        self._images_returned = 0  # Number of images returned in __next__

    def _la_to_rgba(self, la_image: np.ndarray) -> np.ndarray:
        """Convert a Luminance-Alpha (LA) image to RGBA format without losing information."""
        if len(la_image.shape) != 3 or la_image.shape[2] != 2:
            raise ValueError("Input must be an LA image with shape (height, width, 2)")

        height, width, _ = la_image.shape
        rgba_image = np.zeros((height, width, 4), dtype=la_image.dtype)

        # Extract L and A channels
        l_channel = la_image[..., 0]
        a_channel = la_image[..., 1]

        # Copy L channel to R, G, and B channels
        rgba_image[..., 0] = l_channel  # Red
        rgba_image[..., 1] = l_channel  # Green
        rgba_image[..., 2] = l_channel  # Blue
        rgba_image[..., 3] = a_channel  # Alpha

        return rgba_image

    def __iter__(self):
        """Return the iterator object"""
        return self

    def __next__(self):
        """Return the DataChunk with the single full image"""
        from PIL import Image

        if self._images_returned == 0:
            data = np.asarray(Image.open(self._file_path))

            # Transform LA to RGBA if needed
            if self.image_mode == "LA":
                data = self._la_to_rgba(data)

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
    def image_info(self):
        """Return dictionary with image information"""
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
    associated_suffixes = (".png", ".jpg", ".jpeg", ".tiff", ".tif", "webp")
    info = "Interface for converting single or multiple images to NWB format."

    # Mapping from PIL mode to NWB image class
    IMAGE_MODE_TO_NWB_TYPE_MAP = {
        "L": GrayscaleImage,  # 8 bit grayscale image
        "RGB": RGBImage,
        "RGBA": RGBAImage,
        "LA": RGBAImage,  # LA will be converted to RGBA
        "I;16": GrayscaleImage,  # 16-bit grayscale image
    }

    @classmethod
    def get_source_schema(cls) -> dict:
        """Return the schema for the source_data."""
        return dict(
            required=["file_paths"],
            properties=dict(
                file_paths=dict(
                    type="array",
                    items=dict(type="string"),
                    description="List of paths to image files to be converted",
                ),
                folder_path=dict(
                    type="string",
                    description="Path to folder containing images to be converted. Used if file_paths not provided.",
                ),
            ),
        )

    def __init__(
        self,
        file_paths: list[str | Path] | None = None,
        folder_path: str | Path | None = None,
        images_location: Literal["acquisition", "stimulus"] = "acquisition",
        images_container_metadata_key: str = "Images",
        verbose: bool = True,
    ):
        """
        Initialize the ImageInterface.

        Parameters
        ----------
        file_paths : list of str | Path, optional
            List of paths to image files to be converted
        folder_path : str | Path, optional
            Path to folder containing images to be converted. Used if file_paths not provided.
        images_location : Literal["acquisition", "stimulus"], default: "acquisition"
            Location to store images in the NWB file
        images_container_metadata_key : str, default: "Images"
            Key to use in metadata["Images"][images_container_metadata_key] for storing container metadata
        verbose : bool, default: True
            Whether to print status messages
        """
        if file_paths is None and folder_path is None:
            raise ValueError("Either file_paths or folder_path must be provided")

        if file_paths is not None and folder_path is not None:
            raise ValueError("Only one of file_paths or folder_path should be provided")

        self.file_paths = file_paths
        self.folder_path = folder_path
        self.images_location = images_location
        self.images_container_metadata_key = images_container_metadata_key

        super().__init__(
            verbose=verbose,
            file_paths=file_paths,
            folder_path=folder_path,
            images_location=images_location,
            images_container_metadata_key=images_container_metadata_key,
        )

        # Process paths
        if folder_path is not None:
            folder = Path(folder_path)
            if not folder.exists():
                raise ValueError(f"Folder path {folder} does not exist")

            # Get all image files in folder
            file_paths = []
            for suffix in self.associated_suffixes:
                file_paths.extend(folder.glob(f"*{suffix}"))

            if not file_paths:
                raise ValueError(f"No image files found in {folder}")

        self.file_paths = [Path(p).resolve() for p in file_paths]

    def get_metadata(self) -> DeepDict:
        """Get metadata for the images."""
        metadata = super().get_metadata()

        # Add basic metadata about the images under the specified key
        if "Images" not in metadata:
            metadata["Images"] = {}

        metadata["Images"][self.images_container_metadata_key] = dict(
            name=self.images_container_metadata_key, description="Images loaded through ImageInterface"
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict | None = None,
        container_name: str | None = None,
    ) -> None:
        """
        Add the image data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the images to
        metadata : dict, optional
            Metadata for the images
        container_name : str, optional, deprecated
            Name of the Images container. This parameter is deprecated and will be removed
            on or after February 2026. Use images_container_metadata_key in __init__ instead.
            If provided, it overrides the name from metadata.
        """

        if container_name is not None:
            warnings.warn(
                "The 'container_name' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'images_container_metadata_key' in the __init__ method instead.",
                FutureWarning,
                stacklevel=2,
            )

        if metadata is None:
            metadata = self.get_metadata()

        # Get metadata for this specific container
        images_metadata = metadata.get("Images", {})
        container_metadata = images_metadata.get(self.images_container_metadata_key, {})

        # Use container_name only if explicitly provided (deprecated), otherwise use metadata
        if container_name is not None:
            name = container_name
        else:
            name = container_metadata.get("name", self.images_container_metadata_key)

        description = container_metadata.get("description", "Images loaded through ImageInterface")

        # Create Images container
        images_container = Images(
            name=name,
            description=description,
        )

        # Process each image
        for file_path in self.file_paths:
            # Create iterator for memory-efficient loading
            iterator = SingleImageIterator(file_path)

            # Get image name from file name
            image_name = Path(file_path).stem

            # Validate mode and get image class
            if iterator.image_mode not in self.IMAGE_MODE_TO_NWB_TYPE_MAP:
                raise ValueError(f"Unsupported image mode: {iterator.image_mode} for image {file_path.name}")

            nwb_image_class = self.IMAGE_MODE_TO_NWB_TYPE_MAP[iterator.image_mode]
            image_container = nwb_image_class(name=image_name, data=iterator)

            # Add to images container
            images_container.add_image(image_container)

        # Add images container to file
        if self.images_location == "acquisition":
            nwbfile.add_acquisition(images_container)
        else:
            nwbfile.add_stimulus(images_container)
