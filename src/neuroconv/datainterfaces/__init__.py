# Ecephys
from .ecephys.neuroscope.neuroscopedatainterface import (
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface,
)
from .ecephys.spikeglx.spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .ecephys.spikegadgets.spikegadgetsdatainterface import SpikeGadgetsRecordingInterface
from .ecephys.spikeinterface.sipickledatainterfaces import (
    SIPickleRecordingInterface,
    SIPickleSortingInterface,
)
from .ecephys.intan.intandatainterface import IntanRecordingInterface
from .ecephys.ced.ceddatainterface import CEDRecordingInterface
from .ecephys.cellexplorer.cellexplorerdatainterface import CellExplorerSortingInterface
from .ecephys.blackrock.blackrockdatainterface import (
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
)
from .ecephys.openephys.openephysdatainterface import (
    OpenEphysRecordingInterface,
    OpenEphysSortingInterface,
)
from .ecephys.axona.axonadatainterface import (
    AxonaRecordingInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingInterface,
)
from .ecephys.neuralynx.neuralynxdatainterface import NeuralynxRecordingInterface, NeuralynxSortingInterface
from .ecephys.phy.phydatainterface import PhySortingInterface
from .ecephys.kilosort.kilosortdatainterface import KilosortSortingInterface
from .ecephys.edf.edfdatainterface import EDFRecordingInterface


# Icephys
from .icephys.abf.abfdatainterface import AbfInterface


# Ophys
from .ophys.caiman.caimandatainterface import CaimanSegmentationInterface
from .ophys.cnmfe.cnmfedatainterface import CnmfeSegmentationInterface
from .ophys.suite2p.suite2pdatainterface import Suite2pSegmentationInterface
from .ophys.extract.extractdatainterface import ExtractSegmentationInterface
from .ophys.sima.simadatainterface import SimaSegmentationInterface

from .ophys.sbx.sbxdatainterface import SbxImagingInterface
from .ophys.tiff.tiffdatainterface import TiffImagingInterface
from .ophys.hdf5.hdf5datainterface import Hdf5ImagingInterface
from .ophys.scanimage.scanimageimaginginterface import ScanImageImagingInterface


# Behavior
from .behavior.movie.moviedatainterface import MovieInterface
from .behavior.deeplabcut.deeplabcutdatainterface import DeepLabCutInterface


interface_list = [
    # Ecephys
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
    NeuroscopeRecordingInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface,
    NeuroscopeLFPInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXLFPInterface,
    SpikeGadgetsRecordingInterface,
    SIPickleRecordingInterface,
    SIPickleSortingInterface,
    IntanRecordingInterface,
    CEDRecordingInterface,
    CellExplorerSortingInterface,
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
    OpenEphysRecordingInterface,
    OpenEphysSortingInterface,
    PhySortingInterface,
    KilosortSortingInterface,
    AxonaRecordingInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingInterface,
    EDFRecordingInterface,
    # Icephys
    AbfInterface,
    # Ophys
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface,
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    ScanImageImagingInterface,
    # Behavior
    MovieInterface,
    DeepLabCutInterface,
]
