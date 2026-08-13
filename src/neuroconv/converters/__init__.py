"""
Converters are easy-to-use all-in-one classes for handling multi-stream data.

They are collections of particular data interfaces that commonly occur together (such as AP/LF bands of SpikeGLX
or one photon and behavior videos of Miniscope), yet the objects behave just as a normal interfaces do (multiple
converters can still be combined into a parent converter for a dataset).
"""

from ..datainterfaces.behavior.dannce.dannceconverter import DANNCEConverter
from ..datainterfaces.behavior.lightningpose.lightningposeconverter import (
    LightningPoseConverter,
)
from ..datainterfaces.icephys.axon.axonintracellularconverter import AxonIntracellularConverter
from ..datainterfaces.icephys.brukervoltagerecording.brukervoltagerecordingconverter import (
    BrukerVoltageRecordingConverter,
)
from ..datainterfaces.ecephys.sortedrecordinginterface import SortedRecordingConverter
from ..datainterfaces.ecephys.spikeglx.sorted_spikeglx_converter import SortedSpikeGLXConverter
from ..datainterfaces.ecephys.intan.intanconverter import IntanConverter
from ..datainterfaces.ecephys.openephys.openephysbinaryconverter import OpenEphysBinaryConverter
from ..datainterfaces.ecephys.spikeglx.spikeglxconverter import SpikeGLXConverterPipe
from ..datainterfaces.fiber_photometry.guppy.guppyconverter import GuppyConverter
from ..datainterfaces.ophys.brukertiff.brukertiffconverter import (
    BrukerTiffConverter,
    BrukerTiffMultiPlaneConverter,
    BrukerTiffSinglePlaneConverter,
)
from ..datainterfaces.ophys.miniscope.miniscopeconverter import MiniscopeConverter
from ..datainterfaces.ophys.scanimage.scanimageconverter import ScanImageConverter
from ..datainterfaces.ophys.suite2p.suite2pconverter import Suite2pConverter
from ..datainterfaces.ophys.thor.thorconverter import ThorConverter

converter_list = [
    AxonIntracellularConverter,
    BrukerVoltageRecordingConverter,
    DANNCEConverter,
    IntanConverter,
    LightningPoseConverter,
    OpenEphysBinaryConverter,
    SpikeGLXConverterPipe,
    BrukerTiffConverter,
    BrukerTiffMultiPlaneConverter,
    BrukerTiffSinglePlaneConverter,
    MiniscopeConverter,
    ScanImageConverter,
    Suite2pConverter,
    ThorConverter,
    SortedRecordingConverter,
    SortedSpikeGLXConverter,
    GuppyConverter,
]
