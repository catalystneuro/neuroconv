from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pynwb.image import RGBImage

from neuroconv.datainterfaces.image.imageinterface import ImageInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin


def generate_random_images(
    num_images, width=256, height=256, mode="RGB", seed=None, output_dir="generated_images", format="PNG"
):
    """
    Generate random images using numpy arrays and save them in the specified format.

    Parameters:
    -----------
    num_images : int
        Number of images to generate
    width : int
        Width of the images (default: 256)
    height : int
        Height of the images (default: 256)
    mode : str
        Image mode: '1', 'L', 'P', 'RGB', 'RGBA', 'CMYK', 'YCbCr', 'LAB', 'HSV',
        'I', 'F', 'LA', 'PA', 'RGBX', 'RGBa', 'La', 'I;16', 'I;16L', 'I;16B', 'I;16N'
    seed : int or None
        Random seed for reproducibility (default: None)
    output_dir : str
        Directory to save the generated images (default: "generated_images")
    format : str
        Output format: 'PNG', 'JPEG', 'TIFF', 'BMP', 'WEBP', etc. (default: 'PNG')
    """
    mode_configs = {
        "1": {"channels": 1, "dtype": np.uint8, "max_val": 1},
        "L": {"channels": 1, "dtype": np.uint8, "max_val": 255},
        "P": {"channels": 1, "dtype": np.uint8, "max_val": 255},
        "RGB": {"channels": 3, "dtype": np.uint8, "max_val": 255},
        "RGBA": {"channels": 4, "dtype": np.uint8, "max_val": 255},
        "CMYK": {"channels": 4, "dtype": np.uint8, "max_val": 255},
        "YCbCr": {"channels": 3, "dtype": np.uint8, "max_val": 255},
        "LAB": {"channels": 3, "dtype": np.uint8, "max_val": 255},
        "HSV": {"channels": 3, "dtype": np.uint8, "max_val": 255},
        "I": {"channels": 1, "dtype": np.int32, "max_val": 2**31 - 1},
        "F": {"channels": 1, "dtype": np.float32, "max_val": 1.0},
        "LA": {"channels": 2, "dtype": np.uint8, "max_val": 255},
        "PA": {"channels": 2, "dtype": np.uint8, "max_val": 255},
        "RGBX": {"channels": 4, "dtype": np.uint8, "max_val": 255},
        "RGBa": {"channels": 4, "dtype": np.uint8, "max_val": 255},
        "La": {"channels": 2, "dtype": np.uint8, "max_val": 255},
        "I;16": {"channels": 1, "dtype": np.uint16, "max_val": 65535},
        "I;16L": {"channels": 1, "dtype": np.uint16, "max_val": 65535},
        "I;16B": {"channels": 1, "dtype": np.uint16, "max_val": 65535},
        "I;16N": {"channels": 1, "dtype": np.uint16, "max_val": 65535},
    }

    if mode not in mode_configs:
        raise ValueError(f"Mode must be one of {list(mode_configs.keys())}")

    rng = np.random.default_rng(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for file in output_dir.iterdir():
        if file.is_file():
            file.unlink()

    config = mode_configs[mode]
    format_ext = format.lower()

    for i in range(num_images):
        shape = [height, width]
        if config["channels"] > 1:
            shape.append(config["channels"])

        if config["dtype"] in [np.uint8, np.uint16, np.int32]:
            array = rng.integers(0, config["max_val"] + 1, shape, dtype=config["dtype"])
        else:  # float32
            array = rng.random(shape, dtype=config["dtype"])

        if mode == "HSV":
            array[..., 0] = (array[..., 0].astype(float) / 255 * 360).astype(np.uint8)
        elif mode == "P":
            palette = rng.integers(0, 256, (256, 3), dtype=np.uint8)

        image = Image.fromarray(array, mode=mode)
        if mode == "P":
            image.putpalette(palette.flatten())

        filename = f"{output_dir}/image{i}.{format_ext}"
        image.save(filename, format=format)


class TestImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with RGB images."""

    data_interface_cls = ImageInterface

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path):
        """Create interface with RGB test images."""
        # Generate test RGB images
        generate_random_images(num_images=10, mode="RGB", output_dir=str(tmp_path))
        self.interface_kwargs = dict(folder_path=str(tmp_path))
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding RGB images to NWBFile."""

        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 10
            for image in images_container.images.values():
                assert isinstance(image, RGBImage)
