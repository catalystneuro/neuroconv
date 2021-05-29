from .ecephys.ecephystutorialdatainterface import (
    TutorialRecordingInterface,
    TutorialSortingInterface
)
from .ecephys.neuroscopedatainterface import (
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface
)
from .ecephys.spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .ecephys.sipickledatainterfaces import (
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface
)
from .ecephys.intandatainterface import IntanRecordingInterface
from .ecephys.ceddatainterface import CEDRecordingInterface
from .ecephys.cellexplorerdatainterface import CellExplorerSortingInterface
from .ecephys.blackrockdatainterface import BlackrockRecordingExtractorInterface, BlackrockSortingExtractorInterface
from .ecephys.openephysdatainterface import OpenEphysRecordingExtractorInterface, OpenEphysSortingExtractorInterface
from .ecephys.axonadatainterface import (
    AxonaRecordingExtractorInterface,
    AxonaPositionDataInterface
)

from .ophys.roiextractordatainterface import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface
)
from .ophys.imagingextractorinterface import (
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface
)

from .behavior.moviedatainterface import MovieInterface


interface_list = [
    TutorialRecordingInterface,
    TutorialSortingInterface,
    NeuroscopeRecordingInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface,
    NeuroscopeLFPInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXLFPInterface,
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
    IntanRecordingInterface,
    CEDRecordingInterface,
    CellExplorerSortingInterface,
    BlackrockRecordingExtractorInterface,
    BlackrockSortingExtractorInterface,
    OpenEphysRecordingExtractorInterface,
    OpenEphysSortingExtractorInterface,
    AxonaRecordingExtractorInterface,
    AxonaPositionDataInterface,
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface,
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    MovieInterface
]
