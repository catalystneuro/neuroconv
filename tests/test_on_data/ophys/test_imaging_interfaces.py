import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    FemtonicsImagingInterface,
    Hdf5ImagingInterface,
    InscopixImagingInterface,
    MicroManagerTiffImagingInterface,
    MiniscopeImagingInterface,
    SbxImagingInterface,
    ScanImageImagingInterface,
    ScanImageLegacyImagingInterface,
    ScanImageMultiFileImagingInterface,
    ThorImagingInterface,
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


class TestScanImageImagingInterfaceMultiPlaneChannel1(ScanImageMultiPlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(
        file_paths=[OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"],
        channel_name="Channel 1",
        interleave_slice_samples=True,
    )
    save_directory = OUTPUT_PATH

    photon_series_name = "TwoPhotonSeriesChannel1"
    imaging_plane_name = "ImagingPlaneChannel1"
    expected_two_photon_series_data_shape = (6, 256, 528, 2)
    expected_rate = None  # This is interleaved data so the timestamps are written
    expected_starting_time = None

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


class TestScanImageImagingInterfaceMultiPlaneChannel4(ScanImageMultiPlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(
        file_paths=[OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"],
        channel_name="Channel 4",
        interleave_slice_samples=True,
    )
    save_directory = OUTPUT_PATH

    photon_series_name = "TwoPhotonSeriesChannel4"
    imaging_plane_name = "ImagingPlaneChannel4"
    expected_two_photon_series_data_shape = (6, 256, 528, 2)
    expected_rate = None  # This is interleaved data so the timestamps are written
    expected_starting_time = None

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


class TestScanImageImagingInterfaceSinglePlaneCase(ScanImageSinglePlaneImagingInterfaceMixin):
    data_interface_cls = ScanImageImagingInterface
    save_directory = OUTPUT_PATH
    expected_two_photon_series_data_shape = (6, 256, 528)

    @pytest.fixture(
        params=[
            dict(
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                    channel_name="Channel 1",
                    plane_index=0,
                    interleave_slice_samples=True,
                ),
                expected_photon_series_name="TwoPhotonSeriesChannel1Plane0",
                expected_imaging_plane_name="ImagingPlaneChannel1Plane0",
            ),
            dict(
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                    channel_name="Channel 1",
                    plane_index=1,
                    interleave_slice_samples=True,
                ),
                expected_photon_series_name="TwoPhotonSeriesChannel1Plane1",
                expected_imaging_plane_name="ImagingPlaneChannel1Plane1",
            ),
            dict(
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                    channel_name="Channel 4",
                    plane_index=0,
                    interleave_slice_samples=True,
                ),
                expected_photon_series_name="TwoPhotonSeriesChannel4Plane0",
                expected_imaging_plane_name="ImagingPlaneChannel4Plane0",
            ),
            dict(
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"),
                    channel_name="Channel 4",
                    plane_index=1,
                    interleave_slice_samples=True,
                ),
                expected_photon_series_name="TwoPhotonSeriesChannel4Plane1",
                expected_imaging_plane_name="ImagingPlaneChannel4Plane1",
            ),
        ],
        ids=[
            "Channel1Plane0",
            "Channel1Plane1",
            "Channel4Plane0",
            "Channel4Plane1",
        ],
    )
    def setup_interface(self, request):
        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param["interface_kwargs"]
        self.photon_series_name = request.param["expected_photon_series_name"]
        self.imaging_plane_name = request.param["expected_imaging_plane_name"]
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 9, 22, 12, 51, 34, 124000)


class TestScanImageImagingInterfacesAssertions:

    def test_not_recognized_scanimage_version(self):
        """Test that ValueError is returned when ScanImage version could not be determined from metadata."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif")
        with pytest.raises(
            ValueError,
            match="Unsupported ScanImage version 65536. Supported versions are 3, 4, and 5.Most likely this is a legacy version, use ScanImageLegacyImagingInterface instead.",
        ):
            ScanImageImagingInterface(file_path=file_path)

    def test_not_supported_scanimage_version(self):
        """Test that ValueError is raised for ScanImage version 3.8 when ScanImageSinglePlaneImagingInterface is used."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff")
        with pytest.raises(ValueError, match="ScanImage version 3.8 is not supported."):
            ScanImageSinglePlaneImagingInterface(file_path=file_path)

    def test_channel_name_not_specified(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        with pytest.raises(ValueError, match="Multiple channels available in the data"):
            ScanImageImagingInterface(file_path=file_path)

    def test_channel_name_not_specified_for_multi_plane_data(self):
        """Test that ValueError is raised when channel_name is not specified for data with multiple channels."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        with pytest.raises(ValueError, match="More than one channel is detected!"):
            ScanImageMultiPlaneImagingInterface(file_path=file_path)

    def test_plane_name_not_specified(self):
        """Test that ValueError is raised when plane_name is not specified for data with multiple planes."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        with pytest.raises(ValueError, match="More than one plane is detected!"):
            ScanImageSinglePlaneImagingInterface(file_path=file_path, channel_name="Channel 1")

    def test_incorrect_channel_name(self):
        """Test that ValueError is raised when incorrect channel name is specified."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif")
        channel_name = "Channel 2"
        with pytest.raises(
            ValueError,
            match=r"Channel name \(Channel 2\) not found in available channels \(\['Channel 1', 'Channel 4'\]\)\. Please specify a valid channel name\.",
        ):
            ScanImageImagingInterface(file_path=file_path, channel_name=channel_name, interleave_slice_samples=True)

    def test_incorrect_plane_name(self):
        """Test that ValueError is raised when incorrect plane name is specified."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220801_volume.tif")
        with pytest.raises(ValueError, match=r"plane_index \(20\) must be between 0 and 19"):
            ScanImageImagingInterface(file_path=file_path, plane_name="20")

    def test_non_volumetric_data(self):
        """Test that ValueError is raised for non-volumetric imaging data."""
        file_path = str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20240320_multifile_00001.tif")
        with pytest.raises(
            ValueError,
            match="Only one plane detected. For single plane imaging data use ScanImageSinglePlaneImagingInterface instead.",
        ):
            ScanImageMultiPlaneImagingInterface(file_path=file_path, channel_name="Channel 1")


@pytest.mark.skipif(platform.machine() == "arm64", reason="Interface not supported on arm64 architecture")
class TestScanImageLegacyImagingInterface(ImagingExtractorInterfaceTestMixin):
    data_interface_cls = ScanImageLegacyImagingInterface
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
    expected_rate = 7.28119
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
        with self.assertRaisesRegex(ValueError, r"ScanImage version 3.8 is not supported."):
            # Code here should invoke the functionality that triggers the exception
            # Example:
            interface = ScanImageMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern)
            interface.get_metadata()

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
            emission_lambda=np.nan,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.nan,
            indicator="unknown",
            location="unknown",
            device="bruker_device_default",
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
            imaging_plane_metadata_key="default_imaging_plane_metadata_key",
            scan_line_rate=15840.580398865815,
            field_of_view=[0.0005672, 0.0005672],
        )
        cls.ophys_metadata = dict(
            ImagingPlanes={"default_imaging_plane_metadata_key": cls.imaging_plane_metadata},
            TwoPhotonSeries={"default": cls.two_photon_series_metadata},
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
        cls.num_samples = 5
        cls.image_shape = (512, 512, 2)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.nan,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.nan,
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
            assert photon_series.data.shape == (self.num_samples, *self.image_shape)
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
        cls.num_samples = 5
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.available_streams = dict(channel_streams=["Ch2"], plane_streams=dict(Ch2=["Ch2_000001", "Ch2_000002"]))
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.nan,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2000002",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.nan,
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
            assert photon_series.data.shape == (self.num_samples, *self.image_shape)
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
        cls.num_samples = 10
        cls.image_shape = (512, 512)
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.8.64.200")
        cls.available_streams = dict(channel_streams=["Ch1", "Ch2"], plane_streams=dict())
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.nan,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlaneCh2",
            description="The imaging plane origin_coords units are in the microscope reference frame.",
            excitation_lambda=np.nan,
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
            assert photon_series.data.shape == (self.num_samples, *self.image_shape)
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
            emission_lambda=np.nan,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The plane or volume being imaged by the microscope.",
            excitation_lambda=np.nan,
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


class TestThorImagingInterface(ImagingExtractorInterfaceTestMixin):
    """Test ThorImagingInterface."""

    channel_name = "ChanA"
    optical_series_name: str = f"TwoPhotonSeries{channel_name}"
    data_interface_cls = ThorImagingInterface
    interface_kwargs = dict(
        file_path=str(
            OPHYS_DATA_PATH
            / "imaging_datasets"
            / "ThorlabsTiff"
            / "single_channel_single_plane"
            / "20231018-002"
            / "ChanA_001_001_001_001.tif"
        ),
        channel_name="ChanA",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        """Check that the metadata was extracted correctly."""
        # Check session start time
        assert isinstance(metadata["NWBFile"]["session_start_time"], datetime)
        assert metadata["NWBFile"]["session_start_time"].year == 2023
        assert metadata["NWBFile"]["session_start_time"].month == 10
        assert metadata["NWBFile"]["session_start_time"].day == 18
        assert metadata["NWBFile"]["session_start_time"].hour == 17
        assert metadata["NWBFile"]["session_start_time"].minute == 39
        assert metadata["NWBFile"]["session_start_time"].second == 19

        # Check device metadata
        assert len(metadata["Ophys"]["Device"]) == 1
        device = metadata["Ophys"]["Device"][0]
        assert device["name"] == "ThorMicroscope"
        assert device["description"] == "ThorLabs 2P Microscope running ThorImageLS 5.0.2023.10041"

        # Check imaging plane metadata
        assert len(metadata["Ophys"]["ImagingPlane"]) == 1
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == f"ImagingPlane{self.channel_name}"
        assert imaging_plane["description"] == "2P Imaging Plane"
        assert imaging_plane["device"] == "ThorMicroscope"
        assert "grid_spacing" in imaging_plane
        assert "grid_spacing_unit" in imaging_plane

        # Check optical channel metadata
        assert len(imaging_plane["optical_channel"]) == 1
        optical_channel = imaging_plane["optical_channel"][0]
        assert optical_channel["name"] == self.channel_name

        # Check two photon series metadata
        assert len(metadata["Ophys"]["TwoPhotonSeries"]) == 1
        two_photon_series = metadata["Ophys"]["TwoPhotonSeries"][0]
        assert two_photon_series["name"] == self.optical_series_name


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


skip_on_darwin_arm64 = pytest.mark.skipif(
    platform.system() == "Darwin" and platform.machine() == "arm64",
    reason="The isx package is currently not natively supported on macOS with Apple Silicon. "
    "Installation instructions can be found at: "
    "https://github.com/inscopix/pyisx?tab=readme-ov-file#install",
)
skip_on_python_313 = pytest.mark.skipif(
    sys.version_info >= (3, 13),
    reason="Tests are skipped on Python 3.13 because of incompatibility with the 'isx' module "
    "Requires: Python <3.13, >=3.9)"
    "See:https://github.com/inscopix/pyisx/issues",
)


@skip_on_python_313
@skip_on_darwin_arm64
class TestInscopixImagingInterfaceMovie128x128x100Part1(ImagingExtractorInterfaceTestMixin):
    """Test InscopixImagingInterface with movie_128x128x100_part1.isxd (minimal metadata file)."""

    data_interface_cls = InscopixImagingInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_128x128x100_part1.isxd")
    )
    optical_series_name = "OnePhotonSeries"

    def check_extracted_metadata(self, metadata: dict):
        """Test metadata extraction for file with minimal acquisition info."""

        # NWBFile checks
        nwbfile = metadata["NWBFile"]
        assert nwbfile["session_start_time"] == datetime(1970, 1, 1, 0, 0, 0)
        assert "session_id" not in nwbfile
        assert "experimenter" not in nwbfile

        # Device checks
        device = metadata["Ophys"]["Device"][0]
        assert device["name"] == "Microscope"  # Default metadata because this was not included in the source metadata
        assert "description" not in device or device.get("description", "") == ""

        # ImagingPlane checks
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert (
            imaging_plane["device"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert (
            imaging_plane["description"] == "The plane or volume being imaged by the microscope."
        )  # Default metadata because this was not included in the source metadata

        # Optical channel checks
        optical_channel = imaging_plane["optical_channel"][0]
        assert (
            optical_channel["name"] == "channel_0"
        )  # Default metadata because this was not included in the source metadata
        assert (
            optical_channel["description"] == "An optical channel of the microscope."
        )  # Default metadata because this was not included in the source metadata

        # OnePhotonSeries checks
        ops = metadata["Ophys"]["OnePhotonSeries"][0]
        assert ops["name"] == "OnePhotonSeries"
        assert (
            ops["description"] == "Imaging data from one-photon excitation microscopy."
        )  # Default metadata because this was not included in the source metadata
        assert ops["unit"] == "n.a."  # Default metadata because this was not included in the source metadata
        assert ops["imaging_plane"] == "ImagingPlane"
        assert ops["dimension"] == [128, 128]


@skip_on_python_313
@skip_on_darwin_arm64
class TestInscopixImagingInterfaceMovieLongerThan3Min:
    """Test InscopixImagingInterface with movie_longer_than_3_min.isxd (multiplane file that should raise NotImplementedError)."""

    def test_multiplane_not_implemented_error(self):
        """Test that multiplane ISXD files raise NotImplementedError with proper message."""
        from neuroconv.datainterfaces import InscopixImagingInterface

        interface_kwargs = dict(
            file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_longer_than_3_min.isxd")
        )

        # Test that initialization raises NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            InscopixImagingInterface(**interface_kwargs)

        # Verify the error message contains expected information
        expected_message = (
            "Multiplane ISXD file detected (found 'multiplane' in file).\n"
            "This is a hacky check (not an official ISX API method) and may not be robust.\n"
            "Proper separation logic is not yet implemented in roiextractors.\n"
            "Loading as 2D would result in incorrect data interpretation.\n\n"
            "Please open an issue at:\n"
            "https://github.com/catalystneuro/roiextractors/issues\n\n"
            "Reference: https://github.com/inscopix/pyisx/issues/36"
        )
        assert str(exc_info.value) == expected_message


@skip_on_python_313
@skip_on_darwin_arm64
class TestInscopixImagingInterfaceMultiplaneMovie:
    """Test InscopixImagingInterface with movie_longer_than_3_min.isxd (multiplane file that should raise NotImplementedError)."""

    def test_multiplane_not_implemented_error(self):
        """Test that multiplane ISXD files raise NotImplementedError with proper message."""
        from neuroconv.datainterfaces import InscopixImagingInterface

        interface_kwargs = dict(
            file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "multiplane_movie.isxd")
        )

        # Test that initialization raises NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            InscopixImagingInterface(**interface_kwargs)

        # Verify the error message contains expected information
        expected_message = (
            "Multiplane ISXD file detected (found 'multiplane' in file).\n"
            "This is a hacky check (not an official ISX API method) and may not be robust.\n"
            "Proper separation logic is not yet implemented in roiextractors.\n"
            "Loading as 2D would result in incorrect data interpretation.\n\n"
            "Please open an issue at:\n"
            "https://github.com/catalystneuro/roiextractors/issues\n\n"
            "Reference: https://github.com/inscopix/pyisx/issues/36"
        )
        assert str(exc_info.value) == expected_message


@skip_on_python_313
@skip_on_darwin_arm64
class TestInscopixImagingInterfaceDualColorMovieWithDroppedFrames:
    """Test InscopixImagingInterface with movie_longer_than_3_min.isxd (multiplane file that should raise NotImplementedError)."""

    def test_multiplane_not_implemented_error(self):
        """Test that multiplane ISXD files raise NotImplementedError with proper message."""
        from neuroconv.datainterfaces import InscopixImagingInterface

        interface_kwargs = dict(
            file_path=str(
                OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "dual_color_movie_with_dropped_frames.isxd"
            )
        )

        # Test that initialization raises NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            InscopixImagingInterface(**interface_kwargs)

        # Verify the error message contains expected information
        expected_message = (
            "Multiplane ISXD file detected (found 'multiplane' in file).\n"
            "This is a hacky check (not an official ISX API method) and may not be robust.\n"
            "Proper separation logic is not yet implemented in roiextractors.\n"
            "Loading as 2D would result in incorrect data interpretation.\n\n"
            "Please open an issue at:\n"
            "https://github.com/catalystneuro/roiextractors/issues\n\n"
            "Reference: https://github.com/inscopix/pyisx/issues/36"
        )
        assert str(exc_info.value) == expected_message


@skip_on_python_313
@skip_on_darwin_arm64
class TestInscopixImagingInterfaceMovieU8(ImagingExtractorInterfaceTestMixin):
    """Test InscopixImagingInterface with movie_u8.isxd (minimal metadata file, uint8 dtype)."""

    data_interface_cls = InscopixImagingInterface
    save_directory = OUTPUT_PATH
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_u8.isxd"))
    optical_series_name = "OnePhotonSeries"

    def check_extracted_metadata(self, metadata: dict):
        """Test metadata extraction for uint8 file with minimal acquisition info."""

        # NWBFile checks
        nwbfile = metadata["NWBFile"]
        assert nwbfile["session_start_time"] == datetime(1970, 1, 1, 0, 0, 0)
        assert "session_id" not in nwbfile
        assert "experimenter" not in nwbfile

        # Device checks
        device = metadata["Ophys"]["Device"][0]
        assert device["name"] == "Microscope"  # Default metadata because this was not included in the source metadata
        assert "description" not in device or device.get("description", "") == ""

        # ImagingPlane checks
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert (
            imaging_plane["device"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert (
            imaging_plane["description"] == "The plane or volume being imaged by the microscope."
        )  # Default metadata because this was not included in the source metadata

        # Optical channel checks
        optical_channel = imaging_plane["optical_channel"][0]
        assert (
            optical_channel["name"] == "channel_0"
        )  # Default metadata because this was not included in the source metadata
        assert (
            optical_channel["description"] == "An optical channel of the microscope."
        )  # Default metadata because this was not included in the source metadata

        # OnePhotonSeries checks
        ops = metadata["Ophys"]["OnePhotonSeries"][0]
        assert ops["name"] == "OnePhotonSeries"
        assert (
            ops["description"] == "Imaging data from one-photon excitation microscopy."
        )  # Default metadata because this was not included in the source metadata
        assert ops["unit"] == "n.a."  # Default metadata because this was not included in the source metadata
        assert (
            ops["imaging_plane"] == "ImagingPlane"
        )  # Default metadata because this was not included in the source metadata
        assert ops["dimension"] == [3, 4]


class TestFemtonicsImagingInterfaceP29(ImagingExtractorInterfaceTestMixin):
    """Test FemtonicsImagingInterface with p29.mesc file."""

    data_interface_cls = FemtonicsImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"),
        munit_name="MUnit_0",
        channel_name="UG",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        """Check that the metadata was extracted correctly for p29.mesc."""

        # Check session start time
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 9, 29, 7, 53, 0, 903594, tzinfo=timezone.utc)

        # Check NWBFile metadata
        nwbfile_metadata = metadata["NWBFile"]
        assert nwbfile_metadata["session_description"] == "Session: MSession_0, MUnit: MUnit_0."
        assert nwbfile_metadata["experimenter"] == ["flaviod"]
        assert nwbfile_metadata["session_id"] == "66d53392-8f9a-4229-b661-1ea9b591521e"

        # Check device metadata
        device_metadata = metadata["Ophys"]["Device"][0]
        assert (
            device_metadata["name"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert device_metadata["description"] == "version: MESc 3.3, revision: 4356"

        # Check imaging plane metadata
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert (
            imaging_plane["device"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert imaging_plane["imaging_rate"] == 30.962890625
        assert imaging_plane["grid_spacing"] == [1.7821140546875, 1.7821140546875]
        assert imaging_plane["grid_spacing_unit"] == "µm"

        # Check optical channel metadata
        optical_channel = imaging_plane["optical_channel"][0]
        assert optical_channel["name"] == "UG"
        assert (
            optical_channel["description"]
            == "An optical channel of the microscope. PMT voltage: 65.0V, Warmup time: -0.2s"
        )

        # Check two photon series metadata
        two_photon_series = metadata["Ophys"]["TwoPhotonSeries"][0]
        assert two_photon_series["name"] == "TwoPhotonSeries"
        assert (
            two_photon_series["description"] == "Imaging data from two-photon excitation microscopy."
        )  # Default metadata because this was not included in the source metadata
        assert (
            two_photon_series["unit"] == "n.a."
        )  # Default metadata because this was not included in the source metadata
        assert two_photon_series["dimension"] == [512, 512]

        # Check geometric transformations in imaging plane description
        assert (
            imaging_plane["description"]
            == "The plane or volume being imaged by the microscope. Geometric transformations: translation: [  -456.221198   -456.221198 -11608.54    ], rotation: [0. 0. 0. 1.], labeling_origin: [     0.        0.   -11474.34]"
        )


class TestFemtonicsImagingInterfaceP30(ImagingExtractorInterfaceTestMixin):
    """Test FemtonicsImagingInterface with p30.mesc file."""

    data_interface_cls = FemtonicsImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p30.mesc"),
        munit_name="MUnit_0",
        channel_name="UG",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        """Check that the metadata was extracted correctly for p30.mesc."""

        # Check session start time - different from p29
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 9, 30, 9, 36, 12, 98727, tzinfo=timezone.utc)

        # Check NWBFile metadata
        nwbfile_metadata = metadata["NWBFile"]
        assert nwbfile_metadata["session_description"] == "Session: MSession_0, MUnit: MUnit_0."
        assert nwbfile_metadata["experimenter"] == ["flaviod"]
        assert nwbfile_metadata["session_id"] == "071c1b91-a68a-46b3-8702-b619b1bdb49b"

        # Check device metadata
        device_metadata = metadata["Ophys"]["Device"][0]
        assert (
            device_metadata["name"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert device_metadata["description"] == "version: MESc 3.3, revision: 4356"

        # Check imaging plane metadata
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        assert imaging_plane["name"] == "ImagingPlane"
        assert (
            imaging_plane["device"] == "Microscope"
        )  # Default metadata because this was not included in the source metadata
        assert imaging_plane["imaging_rate"] == 30.962890625
        assert imaging_plane["grid_spacing"] == [1.7821140546875, 1.7821140546875]
        assert imaging_plane["grid_spacing_unit"] == "µm"

        # Check optical channel metadata
        optical_channel = imaging_plane["optical_channel"][0]
        assert optical_channel["name"] == "UG"
        assert (
            optical_channel["description"]
            == "An optical channel of the microscope. PMT voltage: 65.0V, Warmup time: -0.2s"
        )

        # Check two photon series metadata
        two_photon_series = metadata["Ophys"]["TwoPhotonSeries"][0]
        assert two_photon_series["name"] == "TwoPhotonSeries"
        assert (
            two_photon_series["description"] == "Imaging data from two-photon excitation microscopy."
        )  # Default metadata because this was not included in the source metadata
        assert (
            two_photon_series["unit"] == "n.a."
        )  # Default metadata because this was not included in the source metadata
        assert two_photon_series["dimension"] == [512, 512]

        # Check geometric transformations in imaging plane description
        assert (
            imaging_plane["description"]
            == "The plane or volume being imaged by the microscope. Geometric transformations: translation: [  -456.221198   -456.221198 -11425.51    ], rotation: [0. 0. 0. 1.], labeling_origin: [     0.        0.   -11281.89]"
        )


# class TestFemtonicsImagingInterfaceSingleChannel(ImagingExtractorInterfaceTestMixin):
#     """Test FemtonicsImagingInterface with single channel .mesc file."""

#     data_interface_cls = FemtonicsImagingInterface
#     interface_kwargs = dict(
#         file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "single_channel.mesc"),
#         munit_name="MUnit_60",
#     )
#     save_directory = OUTPUT_PATH

#     def check_extracted_metadata(self, metadata: dict):
#         """Check that the metadata was extracted correctly for single channel .mesc file."""

#         # Check session start time
#         assert metadata["NWBFile"]["session_start_time"] == datetime(2014, 3, 3, 15, 21, 57, 18837, tzinfo=timezone.utc)

#         # Check NWBFile metadata
#         nwbfile_metadata = metadata["NWBFile"]
#         assert nwbfile_metadata["session_description"] == "Session: MSession_0, MUnit: MUnit_60."
#         assert nwbfile_metadata["experimenter"] == ["measurement"]
#         assert nwbfile_metadata["session_id"] == "eab55dc7-173e-4fcb-8746-65274f1e5f96"

#         # Check device metadata
#         device_metadata = metadata["Ophys"]["Device"][0]
#         assert (
#             device_metadata["name"] == "Microscope"
#         )  # Default metadata because this was not included in the source metadata
#         assert device_metadata["description"] == "version: MESc 1.0, revision: 1839"

#         # Check imaging plane metadata
#         imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
#         assert imaging_plane["name"] == "ImagingPlane"
#         assert (
#             imaging_plane["device"] == "Microscope"
#         )  # Default metadata because this was not included in the source metadata
#         assert imaging_plane["imaging_rate"] == pytest.approx(31.2, rel=1e-2)
#         assert imaging_plane["grid_spacing"] == [0.8757686997991967, 0.8757686997991966]
#         assert imaging_plane["grid_spacing_unit"] == "µm"

#         # Check optical channel metadata
#         optical_channel = imaging_plane["optical_channel"][0]
#         assert optical_channel["name"] == "UG"
#         assert (
#             optical_channel["description"] == "An optical channel of the microscope."
#         )  # Default metadata because this was not included in the source metadata

#         # Check two photon series metadata
#         two_photon_series = metadata["Ophys"]["TwoPhotonSeries"][0]
#         assert two_photon_series["name"] == "TwoPhotonSeries"
#         assert (
#             two_photon_series["description"] == "Imaging data from two-photon excitation microscopy."
#         )  # Default metadata because this was not included in the source metadata
#         assert (
#             two_photon_series["unit"] == "n.a."
#         )  # Default metadata because this was not included in the source metadata

#         # Image dimensions from metadata: X Dimension: 512 pixels, Y Dimension: 512 pixels
#         assert two_photon_series["dimension"] == [512, 512]

#         # Check geometric transformations in imaging plane description
#         assert (
#             imaging_plane["description"]
#             == "The plane or volume being imaged by the microscope. Geometric transformations: translation: [-224.19678715 -224.19678715    0.        ], rotation: [0. 0. 0. 1.], labeling_origin: [    0.       0.   -6724.23]"
#         )


# class TestFemtonicsImagingInterfaceSingleMUnit(ImagingExtractorInterfaceTestMixin):
#     """Test FemtonicsImagingInterface with second single channel .mesc file."""

#     data_interface_cls = FemtonicsImagingInterface
#     interface_kwargs = dict(
#         file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "single_m_unit_index.mesc"),
#         channel_name="UG",
#     )
#     save_directory = OUTPUT_PATH

#     def check_extracted_metadata(self, metadata: dict):
#         """Check that the metadata was extracted correctly for second single channel .mesc file."""

#         # Check session start time
#         assert metadata["NWBFile"]["session_start_time"] == datetime(2014, 3, 3, 15, 21, 57, 18837, tzinfo=timezone.utc)

#         # Check NWBFile metadata
#         nwbfile_metadata = metadata["NWBFile"]
#         assert nwbfile_metadata["session_description"] == "Session: MSession_0, MUnit: MUnit_60."
#         assert nwbfile_metadata["experimenter"] == ["measurement"]
#         assert nwbfile_metadata["session_id"] == "eab55dc7-173e-4fcb-8746-65274f1e5f96"

#         # Check device metadata
#         device_metadata = metadata["Ophys"]["Device"][0]
#         assert (
#             device_metadata["name"] == "Microscope"
#         )  # Default metadata because this was not included in the source metadata
#         assert device_metadata["description"] == "version: MESc 1.0, revision: 1839"

#         # Check imaging plane metadata
#         imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
#         assert imaging_plane["name"] == "ImagingPlane"
#         assert (
#             imaging_plane["device"] == "Microscope"
#         )  # Default metadata because this was not included in the source metadata
#         assert imaging_plane["imaging_rate"] == pytest.approx(31.2, rel=1e-2)

#         # Grid spacing from Pixel Size X: 0.876 μm, Pixel Size Y: 0.876 μm
#         assert imaging_plane["grid_spacing"] == [0.8757686997991967, 0.8757686997991966]
#         assert imaging_plane["grid_spacing_unit"] == "µm"

#         # Check optical channel metadata
#         optical_channel = imaging_plane["optical_channel"][0]
#         assert optical_channel["name"] == "UG"
#         assert (
#             optical_channel["description"] == "An optical channel of the microscope."
#         )  # Default metadata because this was not included in the source metadata

#         # Check two photon series metadata
#         two_photon_series = metadata["Ophys"]["TwoPhotonSeries"][0]
#         assert two_photon_series["name"] == "TwoPhotonSeries"
#         assert (
#             two_photon_series["description"] == "Imaging data from two-photon excitation microscopy."
#         )  # Default metadata because this was not included in the source metadata
#         assert (
#             two_photon_series["unit"] == "n.a."
#         )  # Default metadata because this was not included in the source metadata

#         # Image dimensions from metadata: X Dimension: 512 pixels, Y Dimension: 512 pixels
#         assert two_photon_series["dimension"] == [512, 512]

#         assert (
#             imaging_plane["description"]
#             == "The plane or volume being imaged by the microscope. Geometric transformations: translation: [-224.19678715 -224.19678715    0.        ], rotation: [0. 0. 0. 1.], labeling_origin: [    0.       0.   -6724.23]"
#         )


class TestFemtonicsImagingInterfaceStaticMethods:
    """Test static methods of FemtonicsImagingInterface."""

    def test_get_available_channels_p29(self):
        """Test getting available channels for p29.mesc."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        channels = FemtonicsImagingInterface.get_available_channels(file_path=file_path)
        assert channels == ["UG", "UR"]

    def test_get_available_sessions_p29(self):
        """Test getting available sessions for p29.mesc."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        sessions = FemtonicsImagingInterface.get_available_sessions(file_path=file_path)
        assert sessions == ["MSession_0"]

    def test_get_available_munits_p29(self):
        """Test getting available units for p29.mesc."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        units = FemtonicsImagingInterface.get_available_munits(file_path=file_path, session_name="MSession_0")
        assert units == ["MUnit_0", "MUnit_1"]

    def test_channel_name_not_specified_multiple_channels(self):
        """Test that ValueError is raised when channel_name is not specified and multiple channels are available."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Multiple channels found in MSession_0/MUnit_0: \['UG', 'UR'\]\. Please specify 'channel_name' to select one\.",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                munit_name="MUnit_0",
            )

    def test_wrong_channel_name(self):
        """Test that ValueError is raised when an invalid channel_name is specified."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Channel 'WRONG_CHANNEL' not found in MSession_0/MUnit_0\. Available: \['UG', 'UR'\]",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                munit_name="MUnit_0",
                channel_name="WRONG_CHANNEL",
            )

    def test_munit_not_specified_with_multiple_units(self):
        """Test that ValueError is raised when munit_name is not specified and multiple units are available."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Multiple units found in session MSession_0 of Femtonics file: .+\. Available units: \['MUnit_0', 'MUnit_1'\]\. Please specify 'munit_name'\.",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                # munit_name not specified
                channel_name="UG",
            )

    def test_wrong_munit_name(self):
        """Test that ValueError is raised when an invalid munit_name is specified."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Specified munit_name 'WRONG_UNIT' not found in session MSession_0 of Femtonics file: .+\. Available units: \['MUnit_0', 'MUnit_1'\]\.",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                munit_name="WRONG_UNIT",
                channel_name="UG",
            )

    def test_wrong_session_name(self):
        """Test that ValueError is raised when an invalid session_name is specified."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Specified session_name 'WRONG_SESSION' not found in Femtonics file: .+\. Available sessions: \['MSession_0'\]\.",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                session_name="WRONG_SESSION",
                munit_name="MUnit_0",
                channel_name="UG",
            )

    def test_channel_name_not_specified_multiple_channels(self):
        """Test that ValueError is raised when channel_name is not specified and multiple channels are available."""
        file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
        with pytest.raises(
            ValueError,
            match=r"Multiple channels found in MSession_0/MUnit_0: \['UG', 'UR'\]\. Please specify 'channel_name' to select one\.",
        ):
            FemtonicsImagingInterface(
                file_path=file_path,
                munit_name="MUnit_0",
            )
