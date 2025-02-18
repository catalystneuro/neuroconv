from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pynwb.image import GrayscaleImage, RGBAImage, RGBImage

from neuroconv.datainterfaces.image.imageinterface import ImageInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin


def generate_random_images(
    num_images, width=256, height=256, mode="RGB", seed=None, output_dir_path="generated_images", format="PNG"
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
    output_dir_path : str
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
    output_dir_path = Path(output_dir_path)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    for file in output_dir_path.iterdir():
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
        filename = output_dir_path / f"image{i}_{format}_{mode}.{format_ext}"
        image.save(filename, format=format)


@pytest.mark.parametrize("format", ["PNG", "JPEG", "TIFF"])
class TestRGBImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with RGB images."""

    data_interface_cls = ImageInterface
    mode = "RGB"

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path, format):
        """Create interface with RGB test images."""
        # Generate test RGB images
        generate_random_images(num_images=5, mode=self.mode, output_dir_path=tmp_path, format=format)
        self.interface_kwargs = dict(folder_path=tmp_path)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding RGB images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, RGBImage)


@pytest.mark.parametrize("format", ["PNG", "JPEG", "TIFF"])
class TestGrayscaleImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with grayscale (mode L) images."""

    data_interface_cls = ImageInterface
    mode = "L"

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path, format):
        """Create interface with grayscale test images."""
        # Generate test grayscale images
        generate_random_images(num_images=5, mode=self.mode, output_dir_path=tmp_path, format=format)
        self.interface_kwargs = dict(folder_path=tmp_path)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding grayscale images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, GrayscaleImage)


@pytest.mark.parametrize("format", ["PNG", "TIFF"])  # JPEG doesn't support RGBA
class TestRGBAImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with RGBA images."""

    data_interface_cls = ImageInterface
    mode = "RGBA"

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path, format):
        """Create interface with RGBA test images."""
        # Generate test RGBA images
        generate_random_images(num_images=5, mode=self.mode, output_dir_path=tmp_path, format=format)
        self.interface_kwargs = dict(folder_path=tmp_path)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding RGBA images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, RGBAImage)


@pytest.mark.parametrize("format", ["PNG", "TIFF"])  # JPEG doesn't support LA
class TestLAtoRGBAImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with LA images being converted to RGBA."""

    data_interface_cls = ImageInterface
    mode = "LA"

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path, format):
        """Create interface with LA test images."""
        # Generate test LA images
        generate_random_images(num_images=5, mode=self.mode, output_dir_path=tmp_path, format=format)
        self.interface_kwargs = dict(folder_path=tmp_path)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding LA images to NWBFile and verifying they are converted to RGBA."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, RGBAImage)
                # Verify the data shape is correct for RGBA (height, width, 4)
                assert image.data.shape[-1] == 4
                # Verify R, G, B channels are equal (since they come from L channel)
                assert np.all(image.data[..., 0] == image.data[..., 1])
                assert np.all(image.data[..., 1] == image.data[..., 2])


class TestMixedModeAndFormatImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with mixed image modes and formats."""

    data_interface_cls = ImageInterface

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path):
        """Create interface with mixed test images."""
        # Generate test images of different modes and formats
        # Create subdirectories for each format to avoid name collisions
        rgb_dir = tmp_path / "rgb"
        gray_dir = tmp_path / "gray"
        rgba_dir = tmp_path / "rgba"
        la_dir = tmp_path / "la"

        # Generate test images in different directories
        generate_random_images(num_images=2, mode="RGB", output_dir_path=rgb_dir, format="PNG")
        generate_random_images(num_images=2, mode="L", output_dir_path=gray_dir, format="PNG")
        generate_random_images(num_images=2, mode="RGBA", output_dir_path=rgba_dir, format="TIFF")
        generate_random_images(num_images=2, mode="LA", output_dir_path=la_dir, format="PNG")

        # Collect all image paths
        file_paths = []
        for dir_path in [rgb_dir, gray_dir, rgba_dir, la_dir]:
            file_paths.extend([str(p) for p in dir_path.glob("*.*")])

        self.interface_kwargs = dict(file_paths=file_paths)
        self.interface = self.data_interface_cls(file_paths=file_paths)

    def check_read_nwb(self, nwbfile_path):
        """Test adding mixed images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["images"]
            assert len(images_container.images) == 8

            # Count instances of each image type
            num_image_types = {
                RGBImage: 0,
                GrayscaleImage: 0,
                RGBAImage: 0,  # This will include both RGBA and converted LA images
            }

            for image in images_container.images.values():
                num_image_types[type(image)] += 1

            # Verify we have the expected number of each type
            assert num_image_types[RGBImage] == 2  # RGB images
            assert num_image_types[GrayscaleImage] == 2  # L images
            assert num_image_types[RGBAImage] == 4  # 2 RGBA + 2 LA converted to RGBA
