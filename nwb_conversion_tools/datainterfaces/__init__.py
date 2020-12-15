from .neuroscopedatainterface import (
    NeuroscopeRecordingInterface,
    NeuroscopeLFPInterface,
    NeuroscopeMultiRecordingTimeInterface,
    NeuroscopeSortingInterface
)
from .spikeglxdatainterface import SpikeGLXRecordingInterface
from .sipickledatainterfaces import (
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface)
from .intandatainterface import IntanRecordingInterface
from .ceddatainterface import CEDRecordingInterface
from .cellexplorerdatainterface import CellExplorerSortingInterface
from .roiextractordatainterface import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface
)


interface_list = [
    NeuroscopeRecordingInterface,
    NeuroscopeSortingInterface,
    SpikeGLXRecordingInterface,
    SIPickleRecordingExtractorInterface,
    SIPickleSortingExtractorInterface,
    IntanRecordingInterface,
    CellExplorerSortingInterface,
    CEDRecordingInterface,
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    Suite2pSegmentationInterface,
    ExtractSegmentationInterface,
    SimaSegmentationInterface
]