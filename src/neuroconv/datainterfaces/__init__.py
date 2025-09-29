# Behavior
from .behavior.audio.audiointerface import AudioInterface
from .behavior.deeplabcut.deeplabcutdatainterface import DeepLabCutInterface
from .behavior.fictrac.fictracdatainterface import FicTracDataInterface
from .behavior.lightningpose.lightningposedatainterface import (
    LightningPoseDataInterface,
)
from .behavior.medpc.medpcdatainterface import MedPCInterface
from .behavior.miniscope.miniscopedatainterface import MiniscopeBehaviorInterface
from .behavior.neuralynx.neuralynx_nvt_interface import NeuralynxNvtInterface
from .behavior.sleap.sleapdatainterface import SLEAPInterface
from .behavior.video.videodatainterface import VideoInterface
from .behavior.video.externalvideointerface import ExternalVideoInterface
from .behavior.video.internalvideointerface import InternalVideoInterface

# Ecephys
from .ecephys.alphaomega.alphaomegadatainterface import AlphaOmegaRecordingInterface
from .ecephys.axon.axondatainterface import AxonRecordingInterface
from .ecephys.axona.axonadatainterface import (
    AxonaLFPDataInterface,
    AxonaPositionDataInterface,
    AxonaRecordingInterface,
    AxonaUnitRecordingInterface,
)
from .ecephys.biocam.biocamdatainterface import BiocamRecordingInterface
from .ecephys.blackrock.blackrockdatainterface import (
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
)
from .ecephys.cellexplorer.cellexplorerdatainterface import (
    CellExplorerLFPInterface,
    CellExplorerRecordingInterface,
    CellExplorerSortingInterface,
)
from .ecephys.edf.edfdatainterface import EDFRecordingInterface
from .ecephys.edf.edfanaloginterface import EDFAnalogInterface
from .ecephys.intan.intandatainterface import IntanRecordingInterface
from .ecephys.intan.intananaloginterface import IntanAnalogInterface
from .ecephys.kilosort.kilosortdatainterface import KiloSortSortingInterface
from .ecephys.maxwell.maxonedatainterface import MaxOneRecordingInterface
from .ecephys.mcsraw.mcsrawdatainterface import MCSRawRecordingInterface
from .ecephys.mearec.mearecdatainterface import MEArecRecordingInterface
from .ecephys.neuralynx.neuralynxdatainterface import (
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
)
from .ecephys.neuroscope.neuroscopedatainterface import (
    NeuroScopeLFPInterface,
    NeuroScopeRecordingInterface,
    NeuroScopeSortingInterface,
)
from .ecephys.openephys.openephybinarysanaloginterface import OpenEphysBinaryAnalogInterface
from .ecephys.openephys.openephysbinarydatainterface import (
    OpenEphysBinaryRecordingInterface,
)
from .ecephys.openephys.openephysdatainterface import OpenEphysRecordingInterface
from .ecephys.openephys.openephyslegacydatainterface import (
    OpenEphysLegacyRecordingInterface,
)
from .ecephys.openephys.openephyssortingdatainterface import OpenEphysSortingInterface
from .ecephys.phy.phydatainterface import PhySortingInterface
from .ecephys.plexon.plexondatainterface import (
    Plexon2RecordingInterface,
    PlexonRecordingInterface,
    PlexonLFPInterface,
    PlexonSortingInterface,
)
from .ecephys.spike2.spike2datainterface import Spike2RecordingInterface
from .ecephys.spikegadgets.spikegadgetsdatainterface import (
    SpikeGadgetsRecordingInterface,
)
from .ecephys.spikeglx.spikeglxdatainterface import SpikeGLXRecordingInterface
from .ecephys.spikeglx.spikeglxnidqinterface import SpikeGLXNIDQInterface
from .ecephys.tdt.tdtdatainterface import TdtRecordingInterface
from .ecephys.whitematter.whitematterdatainterface import WhiteMatterRecordingInterface

# Icephys
from .icephys.abf.abfdatainterface import AbfInterface

# Ophys
from .ophys.brukertiff.brukertiffdatainterface import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
)
from .ophys.caiman.caimandatainterface import CaimanSegmentationInterface
from .ophys.cnmfe.cnmfedatainterface import CnmfeSegmentationInterface
from .ophys.extract.extractdatainterface import ExtractSegmentationInterface
from .ophys.femtonics.femtonicsdatainterface import FemtonicsImagingInterface
from .ophys.hdf5.hdf5datainterface import Hdf5ImagingInterface
from .ophys.inscopix.inscopixsegmentationdatainterface import InscopixSegmentationInterface
from .ophys.inscopix.inscopiximagingdatainterface import InscopixImagingInterface
from .ophys.micromanagertiff.micromanagertiffdatainterface import (
    MicroManagerTiffImagingInterface,
)
from .ophys.minian.miniandatainterface import MinianSegmentationInterface
from .ophys.miniscope.miniscopeimagingdatainterface import MiniscopeImagingInterface
from .ophys.sbx.sbxdatainterface import SbxImagingInterface
from .ophys.scanimage.scanimageimaginginterfaces import (
    ScanImageImagingInterface,
    ScanImageMultiFileImagingInterface,
    ScanImageLegacyImagingInterface,
)
from .ophys.sima.simadatainterface import SimaSegmentationInterface
from .ophys.suite2p.suite2pdatainterface import Suite2pSegmentationInterface
from .ophys.tdt_fp.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from .ophys.tiff.tiffdatainterface import TiffImagingInterface
from .ophys.thor.thordatainterface import ThorImagingInterface

# Image
from .image.imageinterface import ImageInterface

# Text
from .text.csv.csvtimeintervalsinterface import CsvTimeIntervalsInterface
from .text.excel.exceltimeintervalsinterface import ExcelTimeIntervalsInterface

interface_list = [
    # Ecephys
    NeuralynxRecordingInterface,
    NeuralynxSortingInterface,
    NeuroScopeRecordingInterface,
    NeuroScopeSortingInterface,
    NeuroScopeLFPInterface,
    Spike2RecordingInterface,
    SpikeGLXRecordingInterface,
    SpikeGLXNIDQInterface,
    SpikeGadgetsRecordingInterface,
    IntanRecordingInterface,
    IntanAnalogInterface,
    CellExplorerSortingInterface,
    CellExplorerRecordingInterface,
    CellExplorerLFPInterface,
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
    OpenEphysRecordingInterface,
    OpenEphysBinaryRecordingInterface,
    OpenEphysLegacyRecordingInterface,
    OpenEphysSortingInterface,
    OpenEphysBinaryAnalogInterface,
    PhySortingInterface,
    KiloSortSortingInterface,
    AxonaRecordingInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingInterface,
    EDFRecordingInterface,
    EDFAnalogInterface,
    TdtRecordingInterface,
    PlexonRecordingInterface,
    PlexonLFPInterface,
    Plexon2RecordingInterface,
    PlexonSortingInterface,
    BiocamRecordingInterface,
    AlphaOmegaRecordingInterface,
    AxonRecordingInterface,
    MEArecRecordingInterface,
    MCSRawRecordingInterface,
    MaxOneRecordingInterface,
    WhiteMatterRecordingInterface,
    # Icephys
    AbfInterface,
    # Ophys
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    FemtonicsImagingInterface,
    InscopixSegmentationInterface,
    SimaSegmentationInterface,
    Suite2pSegmentationInterface,
    SbxImagingInterface,
    TiffImagingInterface,
    Hdf5ImagingInterface,
    InscopixImagingInterface,
    ScanImageImagingInterface,
    ScanImageLegacyImagingInterface,
    ScanImageMultiFileImagingInterface,
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
    MicroManagerTiffImagingInterface,
    MiniscopeImagingInterface,
    TDTFiberPhotometryInterface,
    MinianSegmentationInterface,
    ThorImagingInterface,
    # Behavior
    VideoInterface,
    ExternalVideoInterface,
    InternalVideoInterface,
    AudioInterface,
    DeepLabCutInterface,
    SLEAPInterface,
    MiniscopeBehaviorInterface,
    FicTracDataInterface,
    NeuralynxNvtInterface,
    LightningPoseDataInterface,
    MedPCInterface,
    # Text
    CsvTimeIntervalsInterface,
    ExcelTimeIntervalsInterface,
    # Image
    ImageInterface,
]

interfaces_by_category = dict(
    ecephys={
        interface.__name__.replace("RecordingInterface", ""): interface  # TODO: use removesuffix when 3.8 is dropped
        for interface in interface_list
        if "Recording" in interface.__name__
    },
    sorting={
        interface.__name__.replace("SortingInterface", ""): interface
        for interface in interface_list
        if "Sorting" in interface.__name__
    },
    imaging={
        interface.__name__.replace("ImagingInterface", ""): interface
        for interface in interface_list
        if "Imaging" in interface.__name__
    },
    segmentation={
        interface.__name__.replace("SegmentationInterface", ""): interface
        for interface in interface_list
        if "Segmentation" in interface.__name__
    },
    fiber_photometry={"TDTFiberPhotometry": TDTFiberPhotometryInterface},
    analog=dict(
        OpenEphysAnalog=OpenEphysBinaryAnalogInterface,
        SpikeGLXNIDQ=SpikeGLXNIDQInterface,
        IntanAnalog=IntanAnalogInterface,
    ),
    icephys=dict(Abf=AbfInterface),
    behavior=dict(
        Video=VideoInterface,
        ExternalVideo=ExternalVideoInterface,
        InternalVideo=InternalVideoInterface,
        DeepLabCut=DeepLabCutInterface,
        SLEAP=SLEAPInterface,
        FicTrac=FicTracDataInterface,
        LightningPose=LightningPoseDataInterface,
        # Text
        CsvTimeIntervals=CsvTimeIntervalsInterface,
        ExcelTimeIntervals=ExcelTimeIntervalsInterface,
        MedPC=MedPCInterface,
    ),
    image=dict(
        Image=ImageInterface,
    ),
)
