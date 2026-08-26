"""Interface for converting single or multiple images to NWB format."""

import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from hdmf.data_utils import AbstractDataChunkIterator, DataChunk
from pynwb.base import Image
from pynwb.image import GrayscaleImage, RGBAImage, RGBImage

from .baseimageinterface import BaseImageInterface

# Map PIL image mode -> numpy dtype, for modes supported by ImageInterface.
_PIL_MODE_TO_NUMPY_DTYPE = {
    "L": np.uint8,
    "RGB": np.uint8,
    "RGBA": np.uint8,
    "LA": np.uint8,
    "I;16": np.uint16,
}


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

            self.number_of_bands = len(img.getbands())
            if self.number_of_bands > 1:
                self._image_shape += (self.number_of_bands,)

            # For LA mode, adjust shape to RGBA
            if self.image_mode == "LA":
                self._image_shape = self._image_shape[:-1] + (4,)

            self._dtype = np.dtype(_PIL_MODE_TO_NUMPY_DTYPE.get(self.image_mode, np.uint8))

            # Calculate file size in bytes
            self._size_bytes = self._file_path.stat().st_size
            # Calculate approximate memory size when loaded as numpy array
            self._memory_size = np.prod(self._image_shape) * self._dtype.itemsize

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
        return self._dtype

    @property
    def maxshape(self):
        """Property describing the maximum shape of the data array that is being iterated over"""
        # A single image has a fixed shape, so the maximum shape is the image shape itself. Reporting concrete
        # axes (rather than `None`) is also what allows the default chunking and compression estimators in
        # `tools.nwb_helpers` to size a chunk for this dataset.
        return self._image_shape

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


class ImageInterface(BaseImageInterface):
    """Interface for converting single or multiple images to NWB format."""

    display_name = "Image Interface"
    keywords = ("image",)
    associated_suffixes = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp")
    info = "Interface for converting single or multiple images to NWB format."

    # Mapping from PIL mode to NWB image class
    IMAGE_MODE_TO_NWB_TYPE_MAP = {
        "L": GrayscaleImage,  # 8 bit grayscale image
        "RGB": RGBImage,
        "RGBA": RGBAImage,
        "LA": RGBAImage,  # LA will be converted to RGBA
        "I;16": GrayscaleImage,  # 16-bit grayscale image
    }

    def __init__(
        self,
        file_paths: list[str | Path] | None = None,
        folder_path: str | Path | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        images_location: Literal["acquisition", "stimulus"] = "acquisition",
        metadata_key: str = "Images",
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
        metadata_key : str, default: "Images"
            Key to use in metadata["Images"][metadata_key] for storing container metadata
        verbose : bool, default: True
            Whether to print status messages
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "images_location",
                "metadata_key",
                "verbose",
            ]
            num_positional_args_before_args = 2  # file_paths, folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to ImageInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            images_location = positional_values.get("images_location", images_location)
            metadata_key = positional_values.get("metadata_key", metadata_key)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            file_paths=file_paths,
            folder_path=folder_path,
            images_location=images_location,
            metadata_key=metadata_key,
            verbose=verbose,
        )

    def _create_nwb_image(self, *, file_path: Path, image_metadata: dict) -> Image:
        # Create iterator for memory-efficient loading
        iterator = SingleImageIterator(file_path)
        # Validate mode and get image class
        if iterator.image_mode not in self.IMAGE_MODE_TO_NWB_TYPE_MAP:
            raise ValueError(f"Unsupported image mode: {iterator.image_mode} for image {file_path.name}")

        # Build the Image
        nwb_image_class = self.IMAGE_MODE_TO_NWB_TYPE_MAP[iterator.image_mode]
        image_kwargs = dict(data=iterator)
        image_kwargs.update(image_metadata)
        # If name is not available use the file stem
        image_kwargs["name"] = image_kwargs.get("name", Path(file_path).stem)

        return nwb_image_class(**image_kwargs)
