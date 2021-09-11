from .ecephys.tutorial.recordingtutorialdatainterface import RecordingTutorialInterface
from .ecephys.tutorial.sortingtutorialdatainterface import SortingTutorialInterface
from .ecephys.neuroscope.neuroscopedatainterface import (
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface,
)
from .ecephys.spikeglx.spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .ecephys.spikegadgets.spikegadgetsdatainterface import SpikeGadgetsRecordingInterface
from .ecephys.spikeinterface.sipickledatainterfaces import (
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
)
from .ecephys.intan.intandatainterface import IntanRecordingInterface
from .ecephys.ced.ceddatainterface import CEDRecordingInterface
from .ecephys.cellexplorer.cellexplorerdatainterface import CellExplorerSortingInterface
from .ecephys.blackrock.blackrockdatainterface import (
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
)
from .ecephys.openephys.openephysdatainterface import (
    OpenEphysRecordingExtractorInterface,
    OpenEphysSortingExtractorInterface,
)
from .ecephys.axona.axonadatainterface import (
    AxonaRecordingExtractorInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingExtractorInterface,
)
from .ecephys.neuralynx.neuralynxdatainterface import NeuralynxRecordingInterface
from .ecephys.phy.phydatainterface import PhySortingInterface

from .ophys.caiman.caimandatainterface import CaimanSegmentationInterface
from .ophys.cnmfe.cnmfedatainterface import CnmfeSegmentationInterface
from .ophys.suite2p.suite2pdatainterface import Suite2pSegmentationInterface
from .ophys.extract.extractdatainterface import ExtractSegmentationInterface
from .ophys.sima.simadatainterface import SimaSegmentationInterface

from .ophys.sbx.sbxdatainterface import SbxImagingInterface
from .ophys.tiff.tiffdatainterface import TiffImagingInterface
from .ophys.hdf5.hdf5datainterface import Hdf5ImagingInterface

from .behavior.movie.moviedatainterface import MovieInterface


interface_list = [
    RecordingTutorialInterface,
    SortingTutorialInterface,
    NeuralynxRecordingInterface,
    NeuroscopeRecordingInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface,
    NeuroscopeLFPInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXLFPInterface,
    SpikeGadgetsRecordingInterface,
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
    IntanRecordingInterface,
    CEDRecordingInterface,
    CellExplorerSortingInterface,
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
    OpenEphysRecordingExtractorInterface,
    OpenEphysSortingExtractorInterface,
    PhySortingInterface,
    AxonaRecordingExtractorInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingExtractorInterface,
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface,
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    MovieInterface,
]
