"""Interface for writing images to NWB by reference, without embedding their pixel data."""

from pathlib import Path

from pynwb.base import ExternalImage

from .baseimageinterface import BaseImageInterface


class ExternalImageInterface(BaseImageInterface):
    """Interface for writing images to NWB as paths pointing at the files on disk."""

    display_name = "External Image Interface"
    keywords = ("image", "external")
    associated_suffixes = (".png", ".jpg", ".jpeg", ".gif")
    info = "Interface for writing images to NWB by reference, leaving the pixel data in the source files."

    # NWB only allows these three formats on `ExternalImage.image_format`, and PIL's `Image.format` reports
    # them with the same spelling.
    SUPPORTED_IMAGE_FORMATS = ("PNG", "JPEG", "GIF")

    # `image_mode` is a free-form string on `ExternalImage`, so PIL's mode is passed through as it comes.
    # Only the two grayscale spellings are mapped, since neither reads as a color mode outside of PIL.
    PIL_MODE_TO_NWB_IMAGE_MODE = {"L": "grayscale", "I;16": "grayscale"}

    def _read_image_header(self, file_path: Path) -> tuple[str, str]:
        """
        Return the format and the color mode of an image file, as PIL reports them.

        The header carries both, so the pixel data is never decoded. Reading the format from the file rather
        than from its suffix classifies a mislabeled file by what it actually holds.
        """
        from PIL import Image

        with Image.open(file_path) as image:
            return image.format, image.mode

    def _create_nwb_image(self, *, file_path: Path, image_metadata: dict) -> ExternalImage:
        if "resolution" in image_metadata:
            raise ValueError(
                f"Resolution was given for image {file_path.name} but an external image cannot carry one: "
                "`resolution` is declared on NWB's `Image`, which holds pixel data, and not on the `BaseImage` "
                "parent that `ExternalImage` shares with it. Drop the resolution or write the image with "
                "`ImageInterface`, which embeds the pixels."
            )

        image_format, image_mode = self._read_image_header(file_path)

        if image_format not in self.SUPPORTED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported image format: {image_format} for image {file_path.name}. NWB allows only "
                f"{', '.join(self.SUPPORTED_IMAGE_FORMATS)} for an external image. Write this one with "
                "`ImageInterface`, which embeds the pixels and takes any format PIL can read."
            )

        image_kwargs = dict(
            data=str(file_path),
            image_format=image_format,
            image_mode=self.PIL_MODE_TO_NWB_IMAGE_MODE.get(image_mode, image_mode),
        )
        image_kwargs.update(image_metadata)
        # If name is not available use the file stem
        image_kwargs["name"] = image_kwargs.get("name", Path(file_path).stem)

        return ExternalImage(**image_kwargs)
