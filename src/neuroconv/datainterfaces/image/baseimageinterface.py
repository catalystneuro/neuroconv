"""Base interface shared by the interfaces that write a collection of image files to NWB."""

from pathlib import Path
from typing import Literal

from pynwb import NWBFile
from pynwb.base import BaseImage, Images

from ...basedatainterface import BaseDataInterface
from ...utils import DeepDict


class BaseImageInterface(BaseDataInterface):
    """
    Base class for the interfaces that write a collection of image files into an ``Images`` container.

    Subclasses declare the file suffixes they can write in ``associated_suffixes`` and implement
    ``_create_nwb_image``, which turns a single file into the NWB image object placed in the container.
    """

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
        *,
        metadata_key: str = "Images",
        verbose: bool = True,
    ):
        """
        Initialize the image interface.

        Parameters
        ----------
        file_paths : list of str | Path, optional
            List of paths to image files to be converted
        folder_path : str | Path, optional
            Path to folder containing images to be converted. Used if file_paths not provided.
        metadata_key : str, default: "Images"
            Key to use in metadata["Images"][metadata_key] for storing container metadata
        verbose : bool, default: True
            Whether to print status messages
        """
        if file_paths is None and folder_path is None:
            raise ValueError("Either file_paths or folder_path must be provided")

        if file_paths is not None and folder_path is not None:
            raise ValueError("Only one of file_paths or folder_path should be provided")

        self.file_paths = file_paths
        self.folder_path = folder_path
        self.metadata_key = metadata_key
        # Destination set at construction through `ImageInterface`'s deprecated `images_location`.
        # `add_to_nwbfile` falls back to it when its own `parent_container` is not given.
        self.parent_container = None

        super().__init__(
            verbose=verbose,
            file_paths=file_paths,
            folder_path=folder_path,
            metadata_key=metadata_key,
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

        self.file_paths = [Path(p) for p in file_paths]

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the images.

        This method returns a metadata structure that includes both container-level and per-image metadata.
        The per-image metadata allows customization of individual image properties such as name, resolution,
        and description.

        Returns
        -------
        DeepDict
            Metadata dictionary with the following structure:
            {
                "Images": {
                    "<metadata_key>": {
                        "name": str,
                            Name of the Images container (defaults to metadata_key)
                        "description": str,
                            Description of the Images container
                        "images": {
                            "<file_path_1>": {
                                "name": str,
                                    Name for the individual image (defaults to file stem)
                                "resolution": float, optional
                                    Resolution in pixels/cm (can be added by user, embedded images only)
                                "description": str, optional
                                    Description of the individual image (can be added by user)
                            },
                            "<file_path_2>": {
                                ...
                            }
                        }
                    }
                }
            }

        Examples
        --------
        Basic usage:
        >>> interface = ImageInterface(file_paths=["/data/img1.png", "/data/img2.jpg"])
        >>> metadata = interface.get_metadata()
        >>> print(metadata["Images"]["ImagesRGB"]["images"])
        {
            "/data/img1.png": {"name": "img1"},
            "/data/img2.jpg": {"name": "img2"}
        }

        Customizing per-image metadata:
        >>> metadata = interface.get_metadata()
        >>> metadata["Images"]["ImagesRGB"]["images"]["/data/img1.png"]["resolution"] = 2.5
        >>> metadata["Images"]["ImagesRGB"]["images"]["/data/img1.png"]["description"] = "Baseline image"
        >>> metadata["Images"]["ImagesRGB"]["images"]["/data/img2.jpg"]["name"] = "treatment_image"
        >>> interface.add_to_nwbfile(nwbfile, metadata=metadata)

        Notes
        -----
        - The "images" dictionary maps file paths (as strings) to individual image metadata
        - Users can modify the returned metadata to customize image properties before calling add_to_nwbfile()
        - Resolution should be specified in pixels/cm if provided
        - If resolution or description are not specified, they will not be passed to the NWB image objects
        - Image names default to the file stem but can be overridden in the metadata
        """
        metadata = super().get_metadata()

        # Add basic metadata about the images under the specified key
        if "Images" not in metadata:
            metadata["Images"] = {}

        # Create images_dict mapping file_path to individual image metadata
        images_metadata_dict = {}
        for file_path in self.file_paths:
            file_path_str = str(file_path)
            images_metadata_dict[file_path_str] = {
                "name": Path(file_path).stem,  # Default name from file stem
                # Users can add "resolution" and "description" keys as needed
            }

        metadata["Images"][self.metadata_key] = dict(
            name=self.metadata_key,
            description=self._get_default_container_description(),
            images=images_metadata_dict,
        )

        return metadata

    def _get_default_container_description(self) -> str:
        """Return the description used for the ``Images`` container when the metadata does not state one."""
        return f"Images loaded through {self.__class__.__name__}"

    def _create_nwb_image(self, *, file_path: Path, image_metadata: dict) -> BaseImage:
        """
        Build the NWB image object written for a single file.

        Parameters
        ----------
        file_path : Path
            Path of the image file to write.
        image_metadata : dict
            Per-image metadata block for this file, as returned by `get_metadata`.

        Returns
        -------
        BaseImage
            The image object to add to the `Images` container.
        """
        raise NotImplementedError

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict | None = None,
        *,
        parent_container: Literal["acquisition", "stimulus"] | None = None,
    ) -> None:
        """
        Add the image data to an NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the images to
        metadata : dict, optional
            Metadata for the images
        parent_container : {"acquisition", "stimulus"}, optional
            The group of the NWB file the ``Images`` container is written to, "acquisition" by default.
        """
        if parent_container is None:
            parent_container = self.parent_container or "acquisition"

        if parent_container not in {"acquisition", "stimulus"}:
            raise ValueError(f"parent_container must be either 'acquisition' or 'stimulus', not {parent_container}.")

        if metadata is None:
            metadata = self.get_metadata()

        # Get metadata for this specific container
        images_metadata = metadata.get("Images", {})
        container_metadata = images_metadata.get(self.metadata_key, {})

        name = container_metadata.get("name", self.metadata_key)

        description = container_metadata.get("description", self._get_default_container_description())

        # Create Images container
        images_container = Images(
            name=name,
            description=description,
        )

        # Process each image
        images_metadata_dict = container_metadata.get("images", {})
        for file_path in self.file_paths:
            image_metadata = images_metadata_dict.get(str(file_path), {})
            nwb_image = self._create_nwb_image(file_path=file_path, image_metadata=image_metadata)

            # Add to images container
            images_container.add_image(nwb_image)

        # Add images container to nwb file
        if parent_container == "acquisition":
            nwbfile.add_acquisition(images_container)
        else:
            nwbfile.add_stimulus(images_container)
