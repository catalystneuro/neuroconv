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

# Ecephys
from .ecephys.alphaomega.alphaomegadatainterface import AlphaOmegaRecordingInterface
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
from .ecephys.intan.intandatainterface import IntanRecordingInterface
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
    PlexonSortingInterface,
)
from .ecephys.spike2.spike2datainterface import Spike2RecordingInterface
from .ecephys.spikegadgets.spikegadgetsdatainterface import (
    SpikeGadgetsRecordingInterface,
)
from .ecephys.spikeglx.spikeglxdatainterface import SpikeGLXRecordingInterface
from .ecephys.spikeglx.spikeglxnidqinterface import SpikeGLXNIDQInterface
from .ecephys.tdt.tdtdatainterface import TdtRecordingInterface

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
from .ophys.hdf5.hdf5datainterface import Hdf5ImagingInterface
from .ophys.micromanagertiff.micromanagertiffdatainterface import (
    MicroManagerTiffImagingInterface,
)
from .ophys.miniscope.miniscopeimagingdatainterface import MiniscopeImagingInterface
from .ophys.sbx.sbxdatainterface import SbxImagingInterface
from .ophys.scanimage.scanimageimaginginterfaces import (
    ScanImageImagingInterface,
    ScanImageMultiFileImagingInterface,
)
from .ophys.sima.simadatainterface import SimaSegmentationInterface
from .ophys.suite2p.suite2pdatainterface import Suite2pSegmentationInterface
from .ophys.tdt_fp.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from .ophys.tiff.tiffdatainterface import TiffImagingInterface

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
    CellExplorerSortingInterface,
    CellExplorerRecordingInterface,
    CellExplorerLFPInterface,
    BlackrockRecordingInterface,
    BlackrockSortingInterface,
    OpenEphysRecordingInterface,
    OpenEphysBinaryRecordingInterface,
    OpenEphysLegacyRecordingInterface,
    OpenEphysSortingInterface,
    PhySortingInterface,
    KiloSortSortingInterface,
    AxonaRecordingInterface,
    AxonaPositionDataInterface,
    AxonaLFPDataInterface,
    AxonaUnitRecordingInterface,
    EDFRecordingInterface,
    TdtRecordingInterface,
    PlexonRecordingInterface,
    Plexon2RecordingInterface,
    PlexonSortingInterface,
    BiocamRecordingInterface,
    AlphaOmegaRecordingInterface,
    MEArecRecordingInterface,
    MCSRawRecordingInterface,
    MaxOneRecordingInterface,
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
    ScanImageMultiFileImagingInterface,
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
    MicroManagerTiffImagingInterface,
    MiniscopeImagingInterface,
    TDTFiberPhotometryInterface,
    # Behavior
    VideoInterface,
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
    icephys=dict(Abf=AbfInterface),
    behavior=dict(
        Video=VideoInterface,
        DeepLabCut=DeepLabCutInterface,
        SLEAP=SLEAPInterface,
        FicTrac=FicTracDataInterface,
        LightningPose=LightningPoseDataInterface,
        # Text
        CsvTimeIntervals=CsvTimeIntervalsInterface,
        ExcelTimeIntervals=ExcelTimeIntervalsInterface,
        MedPC=MedPCInterface,
    ),
)
