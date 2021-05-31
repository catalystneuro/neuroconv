from .ecephys.tutorial.ecephystutorialdatainterface import (
    TutorialRecordingInterface,
    TutorialSortingInterface
)
from .ecephys.neuroscope.neuroscopedatainterface import (
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface
)
from .ecephys.spikeglx.spikeglxdatainterface import SpikeGLXRecordingInterface, SpikeGLXLFPInterface
from .ecephys.spikeinterface.sipickledatainterfaces import (
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface
)
from .ecephys.intan.intandatainterface import IntanRecordingInterface
from .ecephys.ced.ceddatainterface import CEDRecordingInterface
from .ecephys.cellexplorer.cellexplorerdatainterface import CellExplorerSortingInterface
from .ecephys.blackrock.blackrockdatainterface import BlackrockRecordingExtractorInterface, BlackrockSortingExtractorInterface
from .ecephys.openephys.openephysdatainterface import OpenEphysRecordingExtractorInterface, OpenEphysSortingExtractorInterface
from .ecephys.axona.axonadatainterface import (
    AxonaRecordingExtractorInterface,
    AxonaPositionDataInterface
)

from .ophys.roi.roiextractordatainterface import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface
)
from .ophys.imaging.imagingextractorinterface import (
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface
)

from .behavior.movie.moviedatainterface import MovieInterface


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
