"""
Converters are easy-to-use all-in-one classes for handling multi-stream data.

They are collections of particular data interfaces that commonly occur together (such as AP/LF bands of SpikeGLX
or one photon and behavior videos of Miniscope), yet the objects behave just as a normal interfaces do (multiple
converters can still be combined into a parent converter for a dataset).
"""

from ..datainterfaces.behavior.lightningpose.lightningposeconverter import (
    LightningPoseConverter,
)
from ..datainterfaces.ecephys.sortedrecordinginterface import SortedRecordingConverter
from ..datainterfaces.ecephys.spikeglx.sorted_spikeglx_converter import SortedSpikeGLXConverter
from ..datainterfaces.ecephys.openephys.openephysbinaryconverter import OpenEphysBinaryConverter
from ..datainterfaces.ecephys.spikeglx.spikeglxconverter import SpikeGLXConverterPipe
from ..datainterfaces.ophys.brukertiff.brukertiffconverter import (
    BrukerTiffMultiPlaneConverter,
    BrukerTiffSinglePlaneConverter,
)
from ..datainterfaces.ophys.guppy.tdtfiberphotometryguppyconverter import (
    TDTFiberPhotometryGuppyConverter,
)
from ..datainterfaces.ophys.miniscope.miniscopeconverter import MiniscopeConverter

converter_list = [
    LightningPoseConverter,
    OpenEphysBinaryConverter,
    SpikeGLXConverterPipe,
    BrukerTiffMultiPlaneConverter,
    BrukerTiffSinglePlaneConverter,
    MiniscopeConverter,
    SortedRecordingConverter,
    SortedSpikeGLXConverter,
    TDTFiberPhotometryGuppyConverter,
]
