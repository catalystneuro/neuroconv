from unittest import TestCase

from neuroconv.datainterfaces import AxonaLFPDataInterface, NeuroScopeLFPInterface, SpikeGLXRecordingInterface
from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from .setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH


class TestAxonaLFPDataInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = AxonaLFPDataInterface
    interface_kwargs = dict(file_path=str(DATA_PATH / "axona" / "dataset_unit_spikes" / "20140815-180secs.eeg"))
    save_directory = OUTPUT_PATH


class TestNeuroScopeLFPInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = NeuroScopeLFPInterface
    interface_kwargs = dict(
        file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.eeg"),
        xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
    )
    save_directory = OUTPUT_PATH


class TestSpikeGLXRecordingInterface(RecordingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = SpikeGLXRecordingInterface
    interface_kwargs = dict(
        file_path=str(
            DATA_PATH / "spikeglx" / "Noise4Sam_g0" / "Noise4Sam_g0_imec0" / "Noise4Sam_g0_t0.imec0.lf.bin"
        )
    )
    save_directory = OUTPUT_PATH
