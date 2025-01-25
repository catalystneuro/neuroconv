import platform
from datetime import datetime
from pathlib import Path
from unittest import skipIf

import numpy as np
import pytest
from dateutil.tz import tzoffset
from hdmf.testing import TestCase as hdmf_TestCase
from numpy.testing import assert_array_equal
from parameterized import parameterized_class
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    BrukerTiffMultiPlaneImagingInterface,
    BrukerTiffSinglePlaneImagingInterface,
    Hdf5ImagingInterface,
    MicroManagerTiffImagingInterface,
    MiniscopeImagingInterface,
    SbxImagingInterface,
    ScanImageImagingInterface,
    ScanImageMultiFileImagingInterface,
    TiffImagingInterface,
)
from neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterfaces import (
    ScanImageMultiPlaneImagingInterface,
    ScanImageMultiPlaneMultiFileImagingInterface,
    ScanImageSinglePlaneImagingInterface,
    ScanImageSinglePlaneMultiFileImagingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
    MiniscopeImagingInterfaceMixin,
    ScanImageMultiPlaneImagingInterfaceMixin,
    ScanImageSinglePlaneImagingInterfaceMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


class TestTiffImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = TiffImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"),
        sampling_frequency=15.0,  # typically provided by user
    )
    save_directory = OUTPUT_PATH


@parameterized_class(
    [
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 1",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 4",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel4",
            "imaging_plane_name": "ImagingPlaneChannel4",
        },
    ],
)
class TestScanImageImagingInterfaceMultiPlaneCase(ScanImageMultiPlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
        channel_name="Channel 1",
    )
    save_directory = OUTPUT_PATH

    photon_series_name = "TwoPhotonSeriesChannel1"
    imaging_plane_name = "ImagingPlaneChannel1"
    expected_two_photon_series_data_shape = (6, 256, 528, 2)
    expected_rate = 29.1248
    expected_starting_time = 0.0

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


@parameterized_class(
    [
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 1",
                plane_name="0",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel1Plane0",
            "imaging_plane_name": "ImagingPlaneChannel1Plane0",
        },
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 1",
                plane_name="1",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel1Plane1",
            "imaging_plane_name": "ImagingPlaneChannel1Plane1",
        },
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 4",
                plane_name="0",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel4Plane0",
            "imaging_plane_name": "ImagingPlaneChannel4Plane0",
        },
        {
            "interface_kwargs": dict(
                file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                channel_name="Channel 4",
                plane_name="1",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel4Plane1",
            "imaging_plane_name": "ImagingPlaneChannel4Plane1",
        },
    ],
)
class TestScanImageImagingInterfaceSinglePlaneCase(ScanImageSinglePlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageImagingInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
        channel_name="Channel 1",
        plane_name="0",
    )

    photon_series_name = "TwoPhotonSeriesChannel1Plane0"
    imaging_plane_name = "ImagingPlaneChannel1Plane0"
    expected_two_photon_series_data_shape = (6, 256, 528)

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


class TestScanImageImagingInterfacesAssertions(hdmf_TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_interface_cls = ScanImageImagingInterface

    def test_not_recognized_scanimage_version(self):
        """Test that ValueError is returned when ScanImage version could not be determined from metadata."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif")
        with self.assertRaisesRegex(ValueError, "ScanImage version could not be determined from metadata."):
            self.data_interface_cls(file_path=file_path)

    def test_not_supported_scanimage_version(self):
        """Test that ValueError is raised for ScanImage version 3.8 when ScanImageSinglePlaneImagingInterface is used."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff")
        with self.assertRaisesRegex(ValueError, "ScanImage version 3.8 is not supported."):
            ScanImageSinglePlaneImagingInterface(file_path=file_path)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(file_path=file_path)

    def test_channel_name_not_specified_for_multi_plane_data(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            ScanImageMultiPlaneImagingInterface(file_path=file_path)

    def test_plane_name_not_specified(self):
        """Test that ValueError is raised when plane_name is not specified for data with multiple planes."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        with self.assertRaisesRegex(ValueError, "More than one plane is detected!"):
            ScanImageSinglePlaneImagingInterface(file_path=file_path, channel_name="Channel 1")

    def test_incorrect_channel_name(self):
        """Test that ValueError is raised when incorrect channel name is specified."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        channel_name = "Channel 2"
        with self.assertRaisesRegex(AssertionError, "Channel 'Channel 2' not found in the tiff file."):
            self.data_interface_cls(file_path=file_path, channel_name=channel_name)

    def test_incorrect_plane_name(self):
        """Test that ValueError is raised when incorrect plane name is specified."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220801_volume.tif")
        with self.assertRaisesRegex(AssertionError, "Plane '20' not found in the tiff file"):
            self.data_interface_cls(file_path=file_path, plane_name="20")

    def test_non_volumetric_data(self):
        """Test that ValueError is raised for non-volumetric imaging data."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        with self.assertRaisesRegex(
            ValueError,
            "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneImagingInterface instead.",
        ):
            ScanImageMultiPlaneImagingInterface(file_path=file_path, channel_name="Channel 1")


@skipIf(platform.machine() == "arm64", "Interface not supported on arm64 architecture")
class TestScanImageLegacyImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 10, 9, 16, 57, 7, 967000)
        assert (
            metadata["Ophys"]["TwoPhotonSeries"][0]["description"]
            == '{"state.configPath": "\'C:\\\\Users\\\\Kishore Kuchibhotla\\\\Desktop\\\\FromOld2P_params\\\\ScanImage_cfgfiles\'", "state.configName": "\'Behavior_2channel\'", "state.software.version": "3.8", "state.software.minorRev": "0", "state.software.beta": "1", "state.software.betaNum": "4", "state.acq.externallyTriggered": "0", "state.acq.startTrigInputTerminal": "1", "state.acq.startTrigEdge": "\'Rising\'", "state.acq.nextTrigInputTerminal": "[]", "state.acq.nextTrigEdge": "\'Rising\'", "state.acq.nextTrigAutoAdvance": "0", "state.acq.nextTrigStopImmediate": "1", "state.acq.nextTrigAdvanceGap": "0", "state.acq.pureNextTriggerMode": "0", "state.acq.numberOfZSlices": "1", "state.acq.zStepSize": "187", "state.acq.numAvgFramesSaveGUI": "1", "state.acq.numAvgFramesSave": "1", "state.acq.numAvgFramesDisplay": "1", "state.acq.averaging": "1", "state.acq.averagingDisplay": "0", "state.acq.numberOfFrames": "1220", "state.acq.numberOfRepeats": "Inf", "state.acq.repeatPeriod": "10", "state.acq.stackCenteredOffset": "[]", "state.acq.stackParkBetweenSlices": "0", "state.acq.linesPerFrame": "256", "state.acq.pixelsPerLine": "256", "state.acq.pixelTime": "3.2e-06", "state.acq.binFactor": "16", "state.acq.frameRate": "3.90625", "state.acq.zoomFactor": "2", "state.acq.scanAngleMultiplierFast": "1", "state.acq.scanAngleMultiplierSlow": "1", "state.acq.scanRotation": "0", "state.acq.scanShiftFast": "1.25", "state.acq.scanShiftSlow": "-0.75", "state.acq.xstep": "0.5", "state.acq.ystep": "0.5", "state.acq.staircaseSlowDim": "0", "state.acq.slowDimFlybackFinalLine": "1", "state.acq.slowDimDiscardFlybackLine": "0", "state.acq.msPerLine": "1", "state.acq.fillFraction": "0.8192", "state.acq.samplesAcquiredPerLine": "4096", "state.acq.acqDelay": "8.32e-05", "state.acq.scanDelay": "9e-05", "state.acq.bidirectionalScan": "1", "state.acq.baseZoomFactor": "1", "state.acq.outputRate": "100000", "state.acq.inputRate": "5000000", "state.acq.inputBitDepth": "12", "state.acq.pockelsClosedOnFlyback": "1", "state.acq.pockelsFillFracAdjust": "4e-05", "state.acq.pmtOffsetChannel1": "0.93603515625", "state.acq.pmtOffsetChannel2": "-0.106689453125", "state.acq.pmtOffsetChannel3": "-0.789306640625", "state.acq.pmtOffsetChannel4": "-1.0419921875", "state.acq.pmtOffsetAutoSubtractChannel1": "0", "state.acq.pmtOffsetAutoSubtractChannel2": "0", "state.acq.pmtOffsetAutoSubtractChannel3": "0", "state.acq.pmtOffsetAutoSubtractChannel4": "0", "state.acq.pmtOffsetStdDevChannel1": "0.853812996333255", "state.acq.pmtOffsetStdDevChannel2": "0.87040286645618", "state.acq.pmtOffsetStdDevChannel3": "0.410833641563274", "state.acq.pmtOffsetStdDevChannel4": "0.20894370294704", "state.acq.rboxZoomSetting": "0", "state.acq.acquiringChannel1": "1", "state.acq.acquiringChannel2": "0", "state.acq.acquiringChannel3": "0", "state.acq.acquiringChannel4": "0", "state.acq.savingChannel1": "1", "state.acq.savingChannel2": "0", "state.acq.savingChannel3": "0", "state.acq.savingChannel4": "0", "state.acq.imagingChannel1": "1", "state.acq.imagingChannel2": "0", "state.acq.imagingChannel3": "0", "state.acq.imagingChannel4": "0", "state.acq.maxImage1": "0", "state.acq.maxImage2": "0", "state.acq.maxImage3": "0", "state.acq.maxImage4": "0", "state.acq.inputVoltageRange1": "10", "state.acq.inputVoltageRange2": "10", "state.acq.inputVoltageRange3": "10", "state.acq.inputVoltageRange4": "10", "state.acq.inputVoltageInvert1": "0", "state.acq.inputVoltageInvert2": "0", "state.acq.inputVoltageInvert3": "0", "state.acq.inputVoltageInvert4": "0", "state.acq.numberOfChannelsSave": "1", "state.acq.numberOfChannelsAcquire": "1", "state.acq.maxMode": "0", "state.acq.fastScanningX": "1", "state.acq.fastScanningY": "0", "state.acq.framesPerFile": "Inf", "state.acq.clockExport.frameClockPolarityHigh": "1", "state.acq.clockExport.frameClockPolarityLow": "0", "state.acq.clockExport.frameClockGateSource": "0", "state.acq.clockExport.frameClockEnable": "1", "state.acq.clockExport.frameClockPhaseShiftUS": "0", "state.acq.clockExport.frameClockGated": "0", "state.acq.clockExport.lineClockPolarityHigh": "1", "state.acq.clockExport.lineClockPolarityLow": "0", "state.acq.clockExport.lineClockGatedEnable": "0", "state.acq.clockExport.lineClockGateSource": "0", "state.acq.clockExport.lineClockAutoSource": "1", "state.acq.clockExport.lineClockEnable": "0", "state.acq.clockExport.lineClockPhaseShiftUS": "0", "state.acq.clockExport.lineClockGated": "0", "state.acq.clockExport.pixelClockPolarityHigh": "1", "state.acq.clockExport.pixelClockPolarityLow": "0", "state.acq.clockExport.pixelClockGateSource": "0", "state.acq.clockExport.pixelClockAutoSource": "1", "state.acq.clockExport.pixelClockEnable": "0", "state.acq.clockExport.pixelClockPhaseShiftUS": "0", "state.acq.clockExport.pixelClockGated": "0", "state.init.eom.powerTransitions.timeString": "\'\'", "state.init.eom.powerTransitions.powerString": "\'\'", "state.init.eom.powerTransitions.transitionCountString": "\'\'", "state.init.eom.uncagingPulseImporter.pathnameText": "\'\'", "state.init.eom.uncagingPulseImporter.powerConversionFactor": "1", "state.init.eom.uncagingPulseImporter.lineConversionFactor": "2", "state.init.eom.uncagingPulseImporter.enabled": "0", "state.init.eom.uncagingPulseImporter.currentPosition": "0", "state.init.eom.uncagingPulseImporter.syncToPhysiology": "0", "state.init.eom.powerBoxStepper.pbsArrayString": "\'[]\'", "state.init.eom.uncagingMapper.enabled": "0", "state.init.eom.uncagingMapper.perGrab": "1", "state.init.eom.uncagingMapper.perFrame": "0", "state.init.eom.uncagingMapper.numberOfPixels": "4", "state.init.eom.uncagingMapper.pixelGenerationUserFunction": "\'\'", "state.init.eom.uncagingMapper.currentPixels": "[]", "state.init.eom.uncagingMapper.currentPosition": "[]", "state.init.eom.uncagingMapper.syncToPhysiology": "0", "state.init.eom.numberOfBeams": "0", "state.init.eom.focusLaserList": "\'PockelsCell-1\'", "state.init.eom.grabLaserList": "\'PockelsCell-1\'", "state.init.eom.snapLaserList": "\'PockelsCell-1\'", "state.init.eom.maxPhotodiodeVoltage": "0", "state.init.eom.boxWidth": "[]", "state.init.eom.powerBoxWidthsInMs": "[]", "state.init.eom.min": "[]", "state.init.eom.maxPower": "[]", "state.init.eom.usePowerArray": "0", "state.init.eom.showBoxArray": "[]", "state.init.eom.boxPowerArray": "[]", "state.init.eom.boxPowerOffArray": "[]", "state.init.eom.startFrameArray": "[]", "state.init.eom.endFrameArray": "[]", "state.init.eom.powerBoxNormCoords": "[]", "state.init.eom.powerVsZEnable": "1", "state.init.eom.powerLzArray": "[]", "state.init.eom.powerLzOverride": "0", "state.cycle.cycleOn": "0", "state.cycle.cycleName": "\'\'", "state.cycle.cyclePath": "\'\'", "state.cycle.cycleLength": "2", "state.cycle.numCycleRepeats": "1", "state.motor.motorZEnable": "0", "state.motor.absXPosition": "659.6", "state.motor.absYPosition": "-10386.6", "state.motor.absZPosition": "-8068.4", "state.motor.absZZPosition": "NaN", "state.motor.relXPosition": "0", "state.motor.relYPosition": "0", "state.motor.relZPosition": "-5.99999999999909", "state.motor.relZZPosition": "NaN", "state.motor.distance": "5.99999999999909", "state.internal.averageSamples": "0", "state.internal.highPixelValue1": "16384", "state.internal.lowPixelValue1": "0", "state.internal.highPixelValue2": "16384", "state.internal.lowPixelValue2": "0", "state.internal.highPixelValue3": "500", "state.internal.lowPixelValue3": "0", "state.internal.highPixelValue4": "500", "state.internal.lowPixelValue4": "0", "state.internal.figureColormap1": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap2": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap3": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap4": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.repeatCounter": "0", "state.internal.startupTimeString": "\'10/9/2017 14:38:30.957\'", "state.internal.triggerTimeString": "\'10/9/2017 16:57:07.967\'", "state.internal.softTriggerTimeString": "\'10/9/2017 16:57:07.970\'", "state.internal.triggerTimeFirstString": "\'10/9/2017 16:57:07.967\'", "state.internal.triggerFrameDelayMS": "0", "state.init.eom.powerConversion1": "10", "state.init.eom.rejected_light1": "0", "state.init.eom.photodiodeOffset1": "0", "state.init.eom.powerConversion2": "10", "state.init.eom.rejected_light2": "0", "state.init.eom.photodiodeOffset2": "0", "state.init.eom.powerConversion3": "10", "state.init.eom.rejected_light3": "0", "state.init.eom.photodiodeOffset3": "0", "state.init.voltsPerOpticalDegree": "0.333", "state.init.scanOffsetAngleX": "0", "state.init.scanOffsetAngleY": "0"}'
        )


@parameterized_class(
    [
        {
            "interface_kwargs": dict(
                folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
                file_pattern="scanimage_20220923_roi.tif",
                channel_name="Channel 1",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "interface_kwargs": dict(
                folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
                file_pattern="scanimage_20220923_roi.tif",
                channel_name="Channel 4",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel4",
            "imaging_plane_name": "ImagingPlaneChannel4",
        },
    ],
)
class TestScanImageMultiFileImagingInterfaceMultiPlaneCase(ScanImageMultiPlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageMultiFileImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
        file_pattern="scanimage_20220923_roi.tif",
        channel_name="Channel 1",
    )
    save_directory = OUTPUT_PATH

    photon_series_name = "TwoPhotonSeriesChannel1"
    imaging_plane_name = "ImagingPlaneChannel1"
    expected_two_photon_series_data_shape = (6, 256, 528, 2)
    expected_rate = 29.1248
    expected_starting_time = 0.0

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


@parameterized_class(
    [
        {
            "interface_kwargs": dict(
                folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
                file_pattern="scanimage_20240320_multifile*.tif",
                channel_name="Channel 1",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel1",
            "imaging_plane_name": "ImagingPlaneChannel1",
        },
        {
            "interface_kwargs": dict(
                folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
                file_pattern="scanimage_20240320_multifile*.tif",
                channel_name="Channel 2",
            ),
            "photon_series_name": "TwoPhotonSeriesChannel2",
            "imaging_plane_name": "ImagingPlaneChannel2",
        },
    ],
)
class TestScanImageMultiFileImagingInterfaceSinglePlaneCase(ScanImageSinglePlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageMultiFileImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"),
        file_pattern="scanimage_20240320_multifile*.tif",
        channel_name="Channel 1",
    )
    save_directory = OUTPUT_PATH

    photon_series_name = "TwoPhotonSeriesChannel1"
    imaging_plane_name = "ImagingPlaneChannel1"
    expected_two_photon_series_data_shape = (30, 512, 512)

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2024, 3, 26, 15, 7, 53, 110000)


class TestScanImageMultiFileImagingInterfacesAssertions(hdmf_TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_interface_cls = ScanImageMultiFileImagingInterface

    def test_not_supported_scanimage_version(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "sample_scanimage.tiff"
        with self.assertRaisesRegex(ValueError, "ScanImage version 3.8 is not supported."):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_not_supported_scanimage_version_multiplane(self):
        """Test that the interface raises ValueError for older ScanImage format and suggests to use a different interface."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "sample_scanimage.tiff"
        with self.assertRaisesRegex(
            ValueError, "ScanImage version 3.8 is not supported. Please use ScanImageImagingInterface instead."
        ):
            ScanImageMultiPlaneMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern)

    def test_non_volumetric_data(self):
        """Test that ValueError is raised for non-volumetric imaging data."""

        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20240320_multifile*.tif"
        channel_name = "Channel 1"
        with self.assertRaisesRegex(
            ValueError,
            "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneMultiFileImagingInterface instead.",
        ):
            ScanImageMultiPlaneMultiFileImagingInterface(
                folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name
            )

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20220923_roi.tif"
        with self.assertRaisesRegex(ValueError, "More than one channel is detected!"):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_not_recognized_scanimage_version(self):
        """Test that ValueError is returned when ScanImage version could not be determined from metadata."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif")
        file_pattern = "*.tif"
        with self.assertRaisesRegex(ValueError, "ScanImage version could not be determined from metadata."):
            self.data_interface_cls(folder_path=folder_path, file_pattern=file_pattern)

    def test_plane_name_not_specified(self):
        """Test that ValueError is raised when plane_name is not specified for data with multiple planes."""
        folder_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage")
        file_pattern = "scanimage_20220801_volume.tif"
        with self.assertRaisesRegex(ValueError, "More than one plane is detected!"):
            ScanImageSinglePlaneMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern)


class TestHdf5ImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = Hdf5ImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "hdf5" / "demoMovie.hdf5"))
    save_directory = OUTPUT_PATH


class TestSbxImagingInterfaceMat(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = SbxImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / "sample.mat"))
    save_directory = OUTPUT_PATH


class TestSbxImagingInterfaceSBX(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = SbxImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / "sample.sbx"))

    save_directory = OUTPUT_PATH


class TestBrukerTiffImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
        )
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(cls, request):

        cls = request.cls

        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=29.873732099062256,
            grid_spacing=[1.1078125e-06, 1.1078125e-06],
            origin_coords=[0.0, 0.0],
        )
        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15840.580398865815,
            field_of_view=[0.0005672, 0.0005672],
        )
        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 2, 20, 15, 58, 25)
        assert metadata["Ophys"] == self.ophys_metadata

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            assert self.device_metadata["name"] in nwbfile.devices
            assert nwbfile.devices[self.device_metadata["name"]].description == self.device_metadata["description"]
            assert self.imaging_plane_metadata["name"] in nwbfile.imaging_planes
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            assert optical_channel.name == self.optical_channel_metadata["name"]
            assert optical_channel.description == self.optical_channel_metadata["description"]
            assert imaging_plane.description == self.imaging_plane_metadata["description"]
            assert imaging_plane.imaging_rate == self.imaging_plane_metadata["imaging_rate"]
            assert_array_equal(imaging_plane.grid_spacing[:], self.imaging_plane_metadata["grid_spacing"])
            assert self.two_photon_series_metadata["name"] in nwbfile.acquisition
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            assert two_photon_series.description == self.two_photon_series_metadata["description"]
            assert two_photon_series.unit == self.two_photon_series_metadata["unit"]
            assert two_photon_series.scan_line_rate == self.two_photon_series_metadata["scan_line_rate"]
            assert_array_equal(two_photon_series.field_of_view[:], self.two_photon_series_metadata["field_of_view"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestBrukerTiffImagingInterfaceDualPlaneCase(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = BrukerTiffMultiPlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        ),
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls

        cls.photon_series_name = "TwoPhotonSeries"
        cls.num_frames = 5
        cls.image_shape = (512, 512, 2)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=20.629515014336377,
            grid_spacing=[1.1078125e-06, 1.1078125e-06, 0.00026],
            origin_coords=[56.215, 14.927, 260.0],
        )

        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="The volumetric imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512, 2],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15842.086085895791,
            field_of_view=[0.0005672, 0.0005672, 0.00026],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(
            folder_path=self.interface_kwargs["folder_path"], plane_separation_type="contiguous"
        )

        assert streams == self.available_streams

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 11, 3, 11, 20, 34)
        assert metadata["Ophys"] == self.ophys_metadata

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            assert photon_series.data.shape == (self.num_frames, *self.image_shape)
            np.testing.assert_array_equal(photon_series.dimension[:], self.image_shape)
            assert photon_series.rate == 20.629515014336377


class TestBrukerTiffImagingInterfaceDualPlaneDisjointCase(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
        ),
        stream_name="Ch2_000002",
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(cls, request):

        cls = request.cls

        cls.photon_series_name = "TwoPhotonSeriesCh2000002"
        cls.num_frames = 5
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001", "Ch2_000002"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2000002",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=10.314757507168189,
            grid_spacing=[1.1078125e-06, 1.1078125e-06, 0.00013],
            origin_coords=[56.215, 14.927, 130.0],
        )

        cls.two_photon_series_metadata = dict(
            name=cls.photon_series_name,
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15842.086085895791,
            field_of_view=[0.0005672, 0.0005672, 0.00013],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(folder_path=self.interface_kwargs["folder_path"])
        assert streams == self.available_streams

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 11, 3, 11, 20, 34)
        assert metadata["Ophys"] == self.ophys_metadata

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory
            / f"{self.data_interface_cls.__name__}_{self.test_name}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.interface_kwargs)

        aligned_starting_time = 1.23
        interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        metadata = interface.get_metadata()
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition[self.photon_series_name].starting_time == aligned_starting_time

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            assert photon_series.data.shape == (self.num_frames, *self.image_shape)
            np.testing.assert_array_equal(photon_series.dimension[:], self.image_shape)
            assert photon_series.rate == 10.314757507168189


class TestBrukerTiffImagingInterfaceDualColorCase(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = BrukerTiffSinglePlaneImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
        ),
        stream_name="Ch2",
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(cls, request):

        cls = request.cls
        cls.photon_series_name = "TwoPhotonSeriesCh2"
        cls.num_frames = 10
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.8.64.200")
        cls.available_streams = dict(channel_streams=["Ch1", "Ch2"], plane_streams=dict())
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=29.873615189896864,
            grid_spacing=[1.1078125e-06, 1.1078125e-06],
            origin_coords=[0.0, 0.0],
        )

        cls.two_photon_series_metadata = dict(
            name=cls.photon_series_name,
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="n.a.",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            scan_line_rate=15835.56350852745,
            field_of_view=[0.0005672, 0.0005672],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def run_custom_checks(self):
        # check stream names
        streams = self.data_interface_cls.get_streams(folder_path=self.interface_kwargs["folder_path"])
        assert streams == self.available_streams

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 7, 6, 15, 13, 58)
        assert metadata["Ophys"] == self.ophys_metadata

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()
            photon_series = nwbfile.acquisition[self.photon_series_name]
            assert photon_series.data.shape == (self.num_frames, *self.image_shape)
            np.testing.assert_array_equal(photon_series.dimension[:], self.image_shape)
            assert photon_series.rate == 29.873615189896864

    def check_nwbfile_temporal_alignment(self):
        nwbfile_path = str(
            self.save_directory
            / f"{self.data_interface_cls.__name__}_{self.test_name}_test_starting_time_alignment.nwb"
        )

        interface = self.data_interface_cls(**self.interface_kwargs)

        aligned_starting_time = 1.23
        interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        metadata = interface.get_metadata()
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.acquisition[self.photon_series_name].starting_time == aligned_starting_time


class TestMicroManagerTiffImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = MicroManagerTiffImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "MicroManagerTif" / "TS12_20220407_20hz_noteasy_1")
    )
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls
        cls.device_metadata = dict(name="Microscope")
        cls.optical_channel_metadata = dict(
            name="OpticalChannelDefault",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The plane or volume being imaged by the microscope.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=20.0,
        )
        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="Imaging data from two-photon excitation microscopy.",
            unit="px",
            dimension=[1024, 1024],
            format="tiff",
            imaging_plane=cls.imaging_plane_metadata["name"],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def check_extracted_metadata(self, metadata: dict):

        assert metadata["NWBFile"]["session_start_time"] == datetime(
            2022, 4, 7, 15, 6, 56, 842000, tzinfo=tzoffset(None, -18000)
        )
        assert metadata["Ophys"] == self.ophys_metadata

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        # Assuming you would create and write an NWB file here before reading it back

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            assert self.imaging_plane_metadata["name"] in nwbfile.imaging_planes
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            assert optical_channel.name == self.optical_channel_metadata["name"]
            assert optical_channel.description == self.optical_channel_metadata["description"]
            assert imaging_plane.description == self.imaging_plane_metadata["description"]
            assert imaging_plane.imaging_rate == self.imaging_plane_metadata["imaging_rate"]
            assert self.two_photon_series_metadata["name"] in nwbfile.acquisition
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            assert two_photon_series.description == self.two_photon_series_metadata["description"]
            assert two_photon_series.unit == self.two_photon_series_metadata["unit"]
            assert two_photon_series.format == self.two_photon_series_metadata["format"]
            assert_array_equal(two_photon_series.dimension[:], self.two_photon_series_metadata["dimension"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestMiniscopeImagingInterface(MiniscopeImagingInterfaceMixin):
    data_interface_cls = MiniscopeImagingInterface
    interface_kwargs = dict(folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5"))
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(cls, request):
        cls = request.cls

        cls.device_name = "Miniscope"

        cls.device_metadata = dict(
            name=cls.device_name,
            compression="FFV1",
            deviceType="Miniscope_V3",
            frameRate="15FPS",
            framesPerFile=1000,
            gain="High",
            led0=47,
        )

        cls.imaging_plane_name = "ImagingPlane"
        cls.imaging_plane_metadata = dict(
            name=cls.imaging_plane_name,
            device=cls.device_name,
            imaging_rate=15.0,
        )

        cls.photon_series_name = "OnePhotonSeries"
        cls.photon_series_metadata = dict(
            name=cls.photon_series_name,
            unit="px",
        )

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 10, 7, 15, 3, 28, 635)
        assert metadata["Ophys"]["Device"][0] == self.device_metadata

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane_metadata["name"] == self.imaging_plane_metadata["name"]
        assert imaging_plane_metadata["device"] == self.imaging_plane_metadata["device"]
        assert imaging_plane_metadata["imaging_rate"] == self.imaging_plane_metadata["imaging_rate"]

        one_photon_series_metadata = metadata["Ophys"]["OnePhotonSeries"][0]
        assert one_photon_series_metadata["name"] == self.photon_series_metadata["name"]
        assert one_photon_series_metadata["unit"] == self.photon_series_metadata["unit"]

    def test_incorrect_folder_structure_raises(self):
        folder_path = Path(self.interface_kwargs["folder_path"]) / "15_03_28/BehavCam_2/"
        with pytest.raises(
            AssertionError, match="The main folder should contain at least one subfolder named 'Miniscope'."
        ):
            self.data_interface_cls(folder_path=folder_path)
