# behavior
# from neuroconv.datainterfaces.behavior.deeplabcut import DeepLabCutInterface
from neuroconv.datainterfaces.behavior.movie import MovieInterface

# ecephys
from neuroconv.datainterfaces.ecephys.axona import (
    AxonaRecordingExtractorInterface,
    AxonaLFPDataInterface,
)
from neuroconv.datainterfaces.ecephys.blackrock import (
    BlackrockSortingExtractorInterface,
    BlackrockRecordingExtractorInterface,
)
from neuroconv.datainterfaces.ecephys.cellexplorer import CellExplorerSortingInterface
from neuroconv.datainterfaces.ecephys.ced import CEDRecordingInterface
from neuroconv.datainterfaces.ecephys.edf import EDFRecordingInterface
from neuroconv.datainterfaces.ecephys.intan import IntanRecordingInterface
from neuroconv.datainterfaces.ecephys.neuralynx import (
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
)

from neuroconv.datainterfaces.ecephys.neuroscope import (
    NeuroscopeRecordingInterface,
    NeuroscopeSortingInterface,
)
from neuroconv.datainterfaces.ecephys.openephys import OpenEphysRecordingExtractorInterface
from neuroconv.datainterfaces.ecephys.phy import PhySortingInterface
from neuroconv.datainterfaces.ecephys.kilosort import KilosortSortingInterface
from neuroconv.datainterfaces.ecephys.spikegadgets import SpikeGadgetsRecordingInterface
from neuroconv.datainterfaces.ecephys.spikeglx import SpikeGLXLFPInterface, SpikeGLXRecordingInterface

# icephys
from neuroconv.datainterfaces.icephys.abf import AbfInterface

# ophys
from neuroconv.datainterfaces.ophys.scanimage import ScanImageImagingInterface
from neuroconv.datainterfaces.ophys.tiff import TiffImagingInterface
from neuroconv.datainterfaces.ophys.hdf5 import Hdf5ImagingInterface
from neuroconv.datainterfaces.ophys.sbx import SbxImagingInterface
from neuroconv.datainterfaces.ophys.caiman import CaimanSegmentationInterface
from neuroconv.datainterfaces.ophys.cnmfe import CnmfeSegmentationInterface
from neuroconv.datainterfaces.ophys.extract import ExtractSegmentationInterface
from neuroconv.datainterfaces.ophys.suite2p import Suite2pSegmentationInterface

interface_list = [
    MovieInterface,
    # DeepLabCutInterface,
    AxonaRecordingExtractorInterface,
    AxonaLFPDataInterface,
    BlackrockSortingExtractorInterface,
    BlackrockRecordingExtractorInterface,
    CellExplorerSortingInterface,
    CEDRecordingInterface,
    EDFRecordingInterface,
    IntanRecordingInterface,
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
    NeuroscopeRecordingInterface,
    NeuroscopeSortingInterface,
    OpenEphysRecordingExtractorInterface,
    PhySortingInterface,
    KilosortSortingInterface,
    SpikeGadgetsRecordingInterface,
    SpikeGLXLFPInterface,
    SpikeGLXRecordingInterface,
    AbfInterface,
    ScanImageImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    SbxImagingInterface,
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    Suite2pSegmentationInterface,
]
