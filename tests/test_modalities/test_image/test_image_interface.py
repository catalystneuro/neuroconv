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
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
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
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
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
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
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
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, RGBAImage)
                # Verify the data shape is correct for RGBA (height, width, 4)
                assert image.data.shape[-1] == 4
                # Verify R, G, B channels are equal (since they come from L channel)
                assert np.all(image.data[..., 0] == image.data[..., 1])
                assert np.all(image.data[..., 1] == image.data[..., 2])


@pytest.mark.parametrize("format", ["PNG", "TIFF"])  # JPEG doesn't support 16-bit
class TestI16GrayscaleImageInterface(DataInterfaceTestMixin):
    """Test suite for ImageInterface with 16-bit grayscale (mode I;16) images."""

    data_interface_cls = ImageInterface
    mode = "I;16"

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path, format):
        """Create interface with 16-bit grayscale test images."""
        # Generate test 16-bit grayscale images
        generate_random_images(num_images=5, mode=self.mode, output_dir_path=tmp_path, format=format)
        self.interface_kwargs = dict(folder_path=tmp_path)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def check_read_nwb(self, nwbfile_path):
        """Test adding 16-bit grayscale images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
            assert len(images_container.images) == 5
            for image in images_container.images.values():
                assert isinstance(image, GrayscaleImage)


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
        i16_dir = tmp_path / "i16"

        # Generate test images in different directories
        generate_random_images(num_images=2, mode="RGB", output_dir_path=rgb_dir, format="PNG")
        generate_random_images(num_images=2, mode="L", output_dir_path=gray_dir, format="PNG")
        generate_random_images(num_images=2, mode="RGBA", output_dir_path=rgba_dir, format="TIFF")
        generate_random_images(num_images=2, mode="LA", output_dir_path=la_dir, format="PNG")
        generate_random_images(num_images=2, mode="I;16", output_dir_path=i16_dir, format="TIFF")

        # Collect all image paths
        file_paths = []
        for dir_path in [rgb_dir, gray_dir, rgba_dir, la_dir, i16_dir]:
            file_paths.extend([str(p) for p in dir_path.glob("*.*")])

        self.interface_kwargs = dict(file_paths=file_paths)
        self.interface = self.data_interface_cls(file_paths=file_paths)

    def check_read_nwb(self, nwbfile_path):
        """Test adding mixed images to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly
            assert "Images" in nwbfile.acquisition
            images_container = nwbfile.acquisition["Images"]
            assert len(images_container.images) == 10

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
            assert num_image_types[GrayscaleImage] == 4  # 2 L images + 2 I;16 images
            assert num_image_types[RGBAImage] == 4  # 2 RGBA + 2 LA converted to RGBA


class TestImagesContainerMetadataKey(DataInterfaceTestMixin):
    """Test suite for ImageInterface with custom images_container_metadata_key."""

    data_interface_cls = ImageInterface

    @pytest.fixture(autouse=True)
    def make_interface(self, tmp_path):
        """Create interface with custom metadata key. This does not use setup_interface because
        setup_interface requires the interface_kwargs to be set in advance and here we don't have them yet.
        """
        # Generate test images
        generate_random_images(num_images=3, mode="RGB", output_dir_path=tmp_path, format="PNG")

        # Create interface with custom metadata key
        self.custom_metadata_key = "CustomImagesKey"
        self.interface_kwargs = dict(folder_path=tmp_path, images_container_metadata_key=self.custom_metadata_key)
        self.interface = self.data_interface_cls(**self.interface_kwargs)

    def test_custom_metadata_key(self):
        """Test that custom metadata key is used correctly."""
        metadata = self.interface.get_metadata()

        # Check that the custom key exists in the metadata
        assert "Images" in metadata
        assert self.custom_metadata_key in metadata["Images"]
        assert metadata["Images"][self.custom_metadata_key]["name"] == self.custom_metadata_key
        assert metadata["Images"][self.custom_metadata_key]["description"] == "Images loaded through ImageInterface"

    def check_read_nwb(self, nwbfile_path):
        """Test adding images with custom metadata key to NWBFile."""
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            # Check images were added correctly - custom key should be used as container name
            assert "CustomImagesKey" in nwbfile.acquisition
            images_container = nwbfile.acquisition["CustomImagesKey"]
            assert len(images_container.images) == 3
            for image in images_container.images.values():
                assert isinstance(image, RGBImage)

    def test_two_interfaces_different_metadata_keys(self, tmp_path):
        """Test that images_container_metadata_key controls metadata and container separation."""
        from pynwb.testing.mock.file import mock_NWBFile

        from neuroconv import ConverterPipe

        # Create separate directories for different image types
        rgb_dir = tmp_path / "rgb_images"
        grayscale_dir = tmp_path / "grayscale_images"
        rgb_dir.mkdir()
        grayscale_dir.mkdir()

        # Generate different types of images
        generate_random_images(num_images=2, mode="RGB", output_dir_path=rgb_dir, format="PNG")
        generate_random_images(num_images=3, mode="L", output_dir_path=grayscale_dir, format="PNG")

        # Create interfaces with different metadata keys
        rgb_interface = ImageInterface(folder_path=rgb_dir, images_container_metadata_key="RGBImages")
        grayscale_interface = ImageInterface(folder_path=grayscale_dir, images_container_metadata_key="GrayscaleImages")

        # Create converter and add to NWB file
        converter = ConverterPipe(
            data_interfaces={"rgb_interface": rgb_interface, "grayscale_interface": grayscale_interface}
        )

        nwbfile = mock_NWBFile()
        converter.add_to_nwbfile(nwbfile=nwbfile, metadata=converter.get_metadata())

        # Verify both containers exist with correct names and content
        assert "RGBImages" in nwbfile.acquisition
        assert "GrayscaleImages" in nwbfile.acquisition
        assert len(nwbfile.acquisition["RGBImages"].images) == 2
        assert len(nwbfile.acquisition["GrayscaleImages"].images) == 3

    def test_per_image_metadata_with_custom_key(self):
        """Test per-image resolution, description, and custom names with custom metadata key."""
        from pynwb.testing.mock.file import mock_NWBFile

        # Get metadata and customize per-image settings using the custom metadata key
        metadata = self.interface.get_metadata()
        images_dict = metadata["Images"][self.custom_metadata_key]["images"]

        # Get file paths from the interface
        file_paths = list(self.interface.file_paths)

        # Set up different metadata for each image
        images_dict[str(file_paths[0])]["resolution"] = 2.5
        images_dict[str(file_paths[0])]["description"] = "First test image"

        images_dict[str(file_paths[1])]["resolution"] = 3.0
        images_dict[str(file_paths[1])]["description"] = "Second test image"
        images_dict[str(file_paths[1])]["name"] = "custom_name_image"

        # Third image gets no custom metadata (should use defaults)

        # Add to NWB file
        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile, metadata=metadata)

        # Verify the images were created with correct metadata in the custom container
        images_container = nwbfile.acquisition[self.custom_metadata_key]
        assert len(images_container.images) == 3

        # Check first image
        first_image_name = file_paths[0].stem
        first_image = images_container.images[first_image_name]
        assert first_image.resolution == 2.5
        assert first_image.description == "First test image"

        # Check second image (with custom name)
        second_image = images_container.images["custom_name_image"]
        assert second_image.resolution == 3.0
        assert second_image.description == "Second test image"

        # Check third image (no custom metadata)
        third_image_name = file_paths[2].stem
        third_image = images_container.images[third_image_name]
        # Should not have resolution or description attributes if not set
        assert not hasattr(third_image, "resolution") or third_image.resolution is None
        assert not hasattr(third_image, "description") or third_image.description is None
