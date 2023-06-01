import platform
from datetime import datetime
from unittest import TestCase, skipIf

import numpy as np
from dateutil.tz import tzoffset
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    BrukerTiffImagingInterface,
    Hdf5ImagingInterface,
    MicroManagerTiffImagingInterface,
    SbxImagingInterface,
    ScanImageImagingInterface,
    TiffImagingInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    ImagingExtractorInterfaceTestMixin,
)

try:
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH


class TestTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = TiffImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"),
        sampling_frequency=15.0,  # typically provided by user
    )
    save_directory = OUTPUT_PATH


@skipIf(platform.machine() == "arm64", "Interface not supported on arm64 architecture")
class TestScanImageImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2017, 10, 9, 16, 57, 7, 967000)
        assert (
            metadata["Ophys"]["TwoPhotonSeries"][0]["description"]
            == '{"state.configPath": "\'C:\\\\Users\\\\Kishore Kuchibhotla\\\\Desktop\\\\FromOld2P_params\\\\ScanImage_cfgfiles\'", "state.configName": "\'Behavior_2channel\'", "state.software.version": "3.8", "state.software.minorRev": "0", "state.software.beta": "1", "state.software.betaNum": "4", "state.acq.externallyTriggered": "0", "state.acq.startTrigInputTerminal": "1", "state.acq.startTrigEdge": "\'Rising\'", "state.acq.nextTrigInputTerminal": "[]", "state.acq.nextTrigEdge": "\'Rising\'", "state.acq.nextTrigAutoAdvance": "0", "state.acq.nextTrigStopImmediate": "1", "state.acq.nextTrigAdvanceGap": "0", "state.acq.pureNextTriggerMode": "0", "state.acq.numberOfZSlices": "1", "state.acq.zStepSize": "187", "state.acq.numAvgFramesSaveGUI": "1", "state.acq.numAvgFramesSave": "1", "state.acq.numAvgFramesDisplay": "1", "state.acq.averaging": "1", "state.acq.averagingDisplay": "0", "state.acq.numberOfFrames": "1220", "state.acq.numberOfRepeats": "Inf", "state.acq.repeatPeriod": "10", "state.acq.stackCenteredOffset": "[]", "state.acq.stackParkBetweenSlices": "0", "state.acq.linesPerFrame": "256", "state.acq.pixelsPerLine": "256", "state.acq.pixelTime": "3.2e-06", "state.acq.binFactor": "16", "state.acq.frameRate": "3.90625", "state.acq.zoomFactor": "2", "state.acq.scanAngleMultiplierFast": "1", "state.acq.scanAngleMultiplierSlow": "1", "state.acq.scanRotation": "0", "state.acq.scanShiftFast": "1.25", "state.acq.scanShiftSlow": "-0.75", "state.acq.xstep": "0.5", "state.acq.ystep": "0.5", "state.acq.staircaseSlowDim": "0", "state.acq.slowDimFlybackFinalLine": "1", "state.acq.slowDimDiscardFlybackLine": "0", "state.acq.msPerLine": "1", "state.acq.fillFraction": "0.8192", "state.acq.samplesAcquiredPerLine": "4096", "state.acq.acqDelay": "8.32e-05", "state.acq.scanDelay": "9e-05", "state.acq.bidirectionalScan": "1", "state.acq.baseZoomFactor": "1", "state.acq.outputRate": "100000", "state.acq.inputRate": "5000000", "state.acq.inputBitDepth": "12", "state.acq.pockelsClosedOnFlyback": "1", "state.acq.pockelsFillFracAdjust": "4e-05", "state.acq.pmtOffsetChannel1": "0.93603515625", "state.acq.pmtOffsetChannel2": "-0.106689453125", "state.acq.pmtOffsetChannel3": "-0.789306640625", "state.acq.pmtOffsetChannel4": "-1.0419921875", "state.acq.pmtOffsetAutoSubtractChannel1": "0", "state.acq.pmtOffsetAutoSubtractChannel2": "0", "state.acq.pmtOffsetAutoSubtractChannel3": "0", "state.acq.pmtOffsetAutoSubtractChannel4": "0", "state.acq.pmtOffsetStdDevChannel1": "0.853812996333255", "state.acq.pmtOffsetStdDevChannel2": "0.87040286645618", "state.acq.pmtOffsetStdDevChannel3": "0.410833641563274", "state.acq.pmtOffsetStdDevChannel4": "0.20894370294704", "state.acq.rboxZoomSetting": "0", "state.acq.acquiringChannel1": "1", "state.acq.acquiringChannel2": "0", "state.acq.acquiringChannel3": "0", "state.acq.acquiringChannel4": "0", "state.acq.savingChannel1": "1", "state.acq.savingChannel2": "0", "state.acq.savingChannel3": "0", "state.acq.savingChannel4": "0", "state.acq.imagingChannel1": "1", "state.acq.imagingChannel2": "0", "state.acq.imagingChannel3": "0", "state.acq.imagingChannel4": "0", "state.acq.maxImage1": "0", "state.acq.maxImage2": "0", "state.acq.maxImage3": "0", "state.acq.maxImage4": "0", "state.acq.inputVoltageRange1": "10", "state.acq.inputVoltageRange2": "10", "state.acq.inputVoltageRange3": "10", "state.acq.inputVoltageRange4": "10", "state.acq.inputVoltageInvert1": "0", "state.acq.inputVoltageInvert2": "0", "state.acq.inputVoltageInvert3": "0", "state.acq.inputVoltageInvert4": "0", "state.acq.numberOfChannelsSave": "1", "state.acq.numberOfChannelsAcquire": "1", "state.acq.maxMode": "0", "state.acq.fastScanningX": "1", "state.acq.fastScanningY": "0", "state.acq.framesPerFile": "Inf", "state.acq.clockExport.frameClockPolarityHigh": "1", "state.acq.clockExport.frameClockPolarityLow": "0", "state.acq.clockExport.frameClockGateSource": "0", "state.acq.clockExport.frameClockEnable": "1", "state.acq.clockExport.frameClockPhaseShiftUS": "0", "state.acq.clockExport.frameClockGated": "0", "state.acq.clockExport.lineClockPolarityHigh": "1", "state.acq.clockExport.lineClockPolarityLow": "0", "state.acq.clockExport.lineClockGatedEnable": "0", "state.acq.clockExport.lineClockGateSource": "0", "state.acq.clockExport.lineClockAutoSource": "1", "state.acq.clockExport.lineClockEnable": "0", "state.acq.clockExport.lineClockPhaseShiftUS": "0", "state.acq.clockExport.lineClockGated": "0", "state.acq.clockExport.pixelClockPolarityHigh": "1", "state.acq.clockExport.pixelClockPolarityLow": "0", "state.acq.clockExport.pixelClockGateSource": "0", "state.acq.clockExport.pixelClockAutoSource": "1", "state.acq.clockExport.pixelClockEnable": "0", "state.acq.clockExport.pixelClockPhaseShiftUS": "0", "state.acq.clockExport.pixelClockGated": "0", "state.init.eom.powerTransitions.timeString": "\'\'", "state.init.eom.powerTransitions.powerString": "\'\'", "state.init.eom.powerTransitions.transitionCountString": "\'\'", "state.init.eom.uncagingPulseImporter.pathnameText": "\'\'", "state.init.eom.uncagingPulseImporter.powerConversionFactor": "1", "state.init.eom.uncagingPulseImporter.lineConversionFactor": "2", "state.init.eom.uncagingPulseImporter.enabled": "0", "state.init.eom.uncagingPulseImporter.currentPosition": "0", "state.init.eom.uncagingPulseImporter.syncToPhysiology": "0", "state.init.eom.powerBoxStepper.pbsArrayString": "\'[]\'", "state.init.eom.uncagingMapper.enabled": "0", "state.init.eom.uncagingMapper.perGrab": "1", "state.init.eom.uncagingMapper.perFrame": "0", "state.init.eom.uncagingMapper.numberOfPixels": "4", "state.init.eom.uncagingMapper.pixelGenerationUserFunction": "\'\'", "state.init.eom.uncagingMapper.currentPixels": "[]", "state.init.eom.uncagingMapper.currentPosition": "[]", "state.init.eom.uncagingMapper.syncToPhysiology": "0", "state.init.eom.numberOfBeams": "0", "state.init.eom.focusLaserList": "\'PockelsCell-1\'", "state.init.eom.grabLaserList": "\'PockelsCell-1\'", "state.init.eom.snapLaserList": "\'PockelsCell-1\'", "state.init.eom.maxPhotodiodeVoltage": "0", "state.init.eom.boxWidth": "[]", "state.init.eom.powerBoxWidthsInMs": "[]", "state.init.eom.min": "[]", "state.init.eom.maxPower": "[]", "state.init.eom.usePowerArray": "0", "state.init.eom.showBoxArray": "[]", "state.init.eom.boxPowerArray": "[]", "state.init.eom.boxPowerOffArray": "[]", "state.init.eom.startFrameArray": "[]", "state.init.eom.endFrameArray": "[]", "state.init.eom.powerBoxNormCoords": "[]", "state.init.eom.powerVsZEnable": "1", "state.init.eom.powerLzArray": "[]", "state.init.eom.powerLzOverride": "0", "state.cycle.cycleOn": "0", "state.cycle.cycleName": "\'\'", "state.cycle.cyclePath": "\'\'", "state.cycle.cycleLength": "2", "state.cycle.numCycleRepeats": "1", "state.motor.motorZEnable": "0", "state.motor.absXPosition": "659.6", "state.motor.absYPosition": "-10386.6", "state.motor.absZPosition": "-8068.4", "state.motor.absZZPosition": "NaN", "state.motor.relXPosition": "0", "state.motor.relYPosition": "0", "state.motor.relZPosition": "-5.99999999999909", "state.motor.relZZPosition": "NaN", "state.motor.distance": "5.99999999999909", "state.internal.averageSamples": "0", "state.internal.highPixelValue1": "16384", "state.internal.lowPixelValue1": "0", "state.internal.highPixelValue2": "16384", "state.internal.lowPixelValue2": "0", "state.internal.highPixelValue3": "500", "state.internal.lowPixelValue3": "0", "state.internal.highPixelValue4": "500", "state.internal.lowPixelValue4": "0", "state.internal.figureColormap1": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap2": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap3": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.figureColormap4": "\'$scim_colorMap(\'\'gray\'\',8,5)\'", "state.internal.repeatCounter": "0", "state.internal.startupTimeString": "\'10/9/2017 14:38:30.957\'", "state.internal.triggerTimeString": "\'10/9/2017 16:57:07.967\'", "state.internal.softTriggerTimeString": "\'10/9/2017 16:57:07.970\'", "state.internal.triggerTimeFirstString": "\'10/9/2017 16:57:07.967\'", "state.internal.triggerFrameDelayMS": "0", "state.init.eom.powerConversion1": "10", "state.init.eom.rejected_light1": "0", "state.init.eom.photodiodeOffset1": "0", "state.init.eom.powerConversion2": "10", "state.init.eom.rejected_light2": "0", "state.init.eom.photodiodeOffset2": "0", "state.init.eom.powerConversion3": "10", "state.init.eom.rejected_light3": "0", "state.init.eom.photodiodeOffset3": "0", "state.init.voltsPerOpticalDegree": "0.333", "state.init.scanOffsetAngleX": "0", "state.init.scanOffsetAngleY": "0"}'
        )


@skipIf(platform.machine() == "arm64", "Interface not supported on arm64 architecture")
class TestScanImageImagingInterfaceRecent(ImagingExtractorInterfaceTestMixin, TestCase):
    # Second class for ScanImageImagingInterface as recommended easier than modifying the first to check metadata in
    # each of several cases
    data_interface_cls = ScanImageImagingInterface
    interface_kwargs = dict(
        file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220801_volume.tif")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2022, 8, 8, 16, 39, 49, 190000)
        assert (
            metadata["Ophys"]["TwoPhotonSeries"][0]["description"]
            == '{"frameNumbers": "8", "acquisitionNumbers": "1", "frameNumberAcquisition": "8", "frameTimestamps_sec": "0.233288390", "acqTriggerTimestamps_sec": "-1.000000000", "nextFileMarkerTimestamps_sec": "-1.000000000", "endOfAcquisition": "1", "endOfAcquisitionMode": "0", "dcOverVoltage": "0", "epoch": "[2022  8  8 16 56 7.329]", "auxTrigger0": "[]", "auxTrigger1": "[]", "auxTrigger2": "[]", "auxTrigger3": "[]", "I2CData": "{}", "SI.LINE_FORMAT_VERSION": "1", "SI.PREMIUM": "true", "SI.TIFF_FORMAT_VERSION": "4", "SI.VERSION_COMMIT": "\'00ac849a74d5101cc34d41b1129ea49c1eb8b1d1\'", "SI.VERSION_MAJOR": "2022", "SI.VERSION_MINOR": "0", "SI.VERSION_UPDATE": "0", "SI.acqState": "\'grab\'", "SI.acqsPerLoop": "1", "SI.errorMsg": "\'\'", "SI.extTrigEnable": "false", "SI.fieldCurvatureRxs": "[]", "SI.fieldCurvatureRys": "[]", "SI.fieldCurvatureTilt": "0", "SI.fieldCurvatureTip": "0", "SI.fieldCurvatureZs": "[]", "SI.hBeams.enablePowerBox": "false", "SI.hBeams.errorMsg": "\'\'", "SI.hBeams.flybackBlanking": "true", "SI.hBeams.interlaceDecimation": "1", "SI.hBeams.interlaceOffset": "0", "SI.hBeams.lengthConstants": "Inf", "SI.hBeams.name": "\'SI Beams\'", "SI.hBeams.powerBoxEndFrame": "Inf", "SI.hBeams.powerBoxStartFrame": "1", "SI.hBeams.powerFractionLimits": "1", "SI.hBeams.powerFractions": "0.92", "SI.hBeams.powers": "92", "SI.hBeams.pzAdjust": "scanimage.types.BeamAdjustTypes.Exponential", "SI.hBeams.pzFunction": "{\'@scanimage.util.defaultPowerFunction\'}", "SI.hBeams.pzLUTSource": "{\'\'}", "SI.hBeams.reserverInfo": "\'\'", "SI.hBeams.totalNumBeams": "1", "SI.hBeams.userInfo": "\'\'", "SI.hBeams.warnMsg": "\'\'", "SI.hCameraManager.errorMsg": "\'\'", "SI.hCameraManager.name": "\'SI CameraManager\'", "SI.hCameraManager.reserverInfo": "\'\'", "SI.hCameraManager.userInfo": "\'\'", "SI.hCameraManager.warnMsg": "\'\'", "SI.hChannels.channelAdcResolution": "{16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16 16}", "SI.hChannels.channelDisplay": "1", "SI.hChannels.channelInputRange": "{[-1 1] [-1 1]}", "SI.hChannels.channelLUT": "{[-1 3562] [-113 5615] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100] [0 100]}", "SI.hChannels.channelMergeColor": "{\'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\' \'red\'}", "SI.hChannels.channelName": "{\'Channel 1\' \'Channel 2\' \'Channel 3\' \'Channel 4\' \'Channel 5\' \'Channel 6\' \'Channel 7\' \'Channel 8\' \'Channel 9\' \'Channel 10\' \'Channel 11\' \'Channel 12\' \'Channel 13\' \'Channel 14\' \'Channel 15\' \'Channel 16\' \'Channel 17\' \'Channel 18\' \'Channel 19\' \'Channel 20\' \'Channel 21\' \'Channel 22\' \'Channel 23\' \'Channel 24\' \'Channel 25\' \'Channel 26\' \'Channel 27\' \'Channel 28\' \'Channel 29\' \'Channel 30\' \'Channel 31\' \'Channel 32\' \'Channel 33\' \'Channel 34\' \'Channel 35\' \'Channel 36\' \'Channel 37\' \'Channel 38\' \'Channel 39\' \'Channel 40\' \'Channel 41\' \'Channel 42\' \'Channel 43\' \'Channel 44\' \'Channel 45\' \'Channel 46\' \'Channel 47\' \'Channel 48\' \'Channel 49\' \'Channel 50\' \'Channel 51\' \'Channel 52\' \'Channel 53\' \'Channel 54\' \'Channel 55\' \'Channel 56\' \'Channel 57\' \'Channel 58\' \'Channel 59\' \'Channel 60\' \'Channel 61\' \'Channel 62\' \'Channel 63\' \'Channel 64\'}", "SI.hChannels.channelOffset": "[321 -14482]", "SI.hChannels.channelSave": "1", "SI.hChannels.channelSubtractOffset": "[true true]", "SI.hChannels.channelType": "{\'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\' \'stripe\'}", "SI.hChannels.channelsActive": "1", "SI.hChannels.channelsAvailable": "2", "SI.hChannels.errorMsg": "\'\'", "SI.hChannels.loggingEnable": "1", "SI.hChannels.name": "\'SI Channels\'", "SI.hChannels.reserverInfo": "\'\'", "SI.hChannels.userInfo": "\'\'", "SI.hChannels.warnMsg": "\'\'", "SI.hConfigurationSaver.cfgFilename": "\'\'", "SI.hConfigurationSaver.errorMsg": "\'\'", "SI.hConfigurationSaver.name": "\'SI ConfigurationSaver\'", "SI.hConfigurationSaver.reserverInfo": "\'\'", "SI.hConfigurationSaver.userInfo": "\'\'", "SI.hConfigurationSaver.usrFilename": "\'\'", "SI.hConfigurationSaver.warnMsg": "\'\'", "SI.hCoordinateSystems.errorMsg": "\'\'", "SI.hCoordinateSystems.name": "\'SI CoordinateSystems\'", "SI.hCoordinateSystems.reserverInfo": "\'\'", "SI.hCoordinateSystems.userInfo": "\'\'", "SI.hCoordinateSystems.warnMsg": "\'\'", "SI.hCycleManager.cycleIterIdxTotal": "0", "SI.hCycleManager.cyclesCompleted": "0", "SI.hCycleManager.enabled": "false", "SI.hCycleManager.errorMsg": "\'\'", "SI.hCycleManager.itersCompleted": "0", "SI.hCycleManager.name": "\'SI CycleManager\'", "SI.hCycleManager.reserverInfo": "\'\'", "SI.hCycleManager.totalCycles": "1", "SI.hCycleManager.userInfo": "\'\'", "SI.hCycleManager.warnMsg": "\'\'", "SI.hDisplay.autoScaleSaturationFraction": "[0.1 0.01]", "SI.hDisplay.channelsMergeEnable": "false", "SI.hDisplay.channelsMergeFocusOnly": "false", "SI.hDisplay.displayRollingAverageFactor": "8", "SI.hDisplay.displayRollingAverageFactorLock": "false", "SI.hDisplay.enableScanfieldDisplays": "false", "SI.hDisplay.errorMsg": "\'\'", "SI.hDisplay.lineScanHistoryLength": "1000", "SI.hDisplay.name": "\'SI Display\'", "SI.hDisplay.renderer": "\'auto\'", "SI.hDisplay.reserverInfo": "\'\'", "SI.hDisplay.scanfieldDisplayColumns": "5", "SI.hDisplay.scanfieldDisplayRows": "5", "SI.hDisplay.scanfieldDisplayTilingMode": "\'Auto\'", "SI.hDisplay.scanfieldDisplays.enable": "false", "SI.hDisplay.scanfieldDisplays.name": "\'Display 1\'", "SI.hDisplay.scanfieldDisplays.channel": "1", "SI.hDisplay.scanfieldDisplays.roi": "1", "SI.hDisplay.scanfieldDisplays.z": "0", "SI.hDisplay.selectedZs": "[]", "SI.hDisplay.showScanfieldDisplayNames": "true", "SI.hDisplay.userInfo": "\'\'", "SI.hDisplay.volumeDisplayStyle": "\'Tiled\'", "SI.hDisplay.warnMsg": "\'\'", "SI.hFastZ.actuatorLag": "0", "SI.hFastZ.discardFlybackFrames": "false", "SI.hFastZ.enable": "false", "SI.hFastZ.enableFieldCurveCorr": "false", "SI.hFastZ.errorMsg": "\'\'", "SI.hFastZ.flybackTime": "0.07", "SI.hFastZ.hasFastZ": "true", "SI.hFastZ.name": "\'SI FastZ\'", "SI.hFastZ.numDiscardFlybackFrames": "0", "SI.hFastZ.position": "50", "SI.hFastZ.reserverInfo": "\'\'", "SI.hFastZ.userInfo": "\'\'", "SI.hFastZ.volumePeriodAdjustment": "-0.0006", "SI.hFastZ.warnMsg": "\'\'", "SI.hFastZ.waveformType": "\'sawtooth\'", "SI.hIntegrationRoiManager.enable": "false", "SI.hIntegrationRoiManager.enableDisplay": "true", "SI.hIntegrationRoiManager.errorMsg": "\'\'", "SI.hIntegrationRoiManager.integrationHistoryLength": "1000", "SI.hIntegrationRoiManager.name": "\'SI IntegrationRoiManager\'", "SI.hIntegrationRoiManager.outputChannelsEnabled": "[]", "SI.hIntegrationRoiManager.outputChannelsFunctions": "{}", "SI.hIntegrationRoiManager.outputChannelsNames": "{}", "SI.hIntegrationRoiManager.outputChannelsPhysicalNames": "{}", "SI.hIntegrationRoiManager.outputChannelsRoiNames": "{}", "SI.hIntegrationRoiManager.postProcessFcn": "\'@scanimage.components.integrationRois.integrationPostProcessingFcn\'", "SI.hIntegrationRoiManager.reserverInfo": "\'\'", "SI.hIntegrationRoiManager.userInfo": "\'\'", "SI.hIntegrationRoiManager.warnMsg": "\'\'", "SI.hMotionManager.correctionBoundsXY": "[-5 5]", "SI.hMotionManager.correctionBoundsZ": "[-50 50]", "SI.hMotionManager.correctionDeviceXY": "\'galvos\'", "SI.hMotionManager.correctionDeviceZ": "\'fastz\'", "SI.hMotionManager.correctionEnableXY": "false", "SI.hMotionManager.correctionEnableZ": "false", "SI.hMotionManager.correctorClassName": "\'scanimage.components.motionCorrectors.SimpleMotionCorrector\'", "SI.hMotionManager.enable": "false", "SI.hMotionManager.errorMsg": "\'\'", "SI.hMotionManager.estimatorClassName": "\'scanimage.components.motionEstimators.SimpleMotionEstimator\'", "SI.hMotionManager.motionHistoryLength": "100", "SI.hMotionManager.motionMarkersXY": "zeros(0,2)", "SI.hMotionManager.name": "\'SI MotionManager\'", "SI.hMotionManager.reserverInfo": "\'\'", "SI.hMotionManager.resetCorrectionAfterAcq": "true", "SI.hMotionManager.userInfo": "\'\'", "SI.hMotionManager.warnMsg": "\'\'", "SI.hMotionManager.zStackAlignmentFcn": "\'@scanimage.components.motionEstimators.util.alignZRoiData\'", "SI.hMotors.axesPosition": "[44251.1 43604.4 12562]", "SI.hMotors.azimuth": "0", "SI.hMotors.elevation": "0", "SI.hMotors.errorMsg": "\'\'", "SI.hMotors.errorTf": "false", "SI.hMotors.isAligned": "false", "SI.hMotors.isHomed": "true", "SI.hMotors.isRelativeZeroSet": "true", "SI.hMotors.maxZStep": "Inf", "SI.hMotors.minPositionQueryInterval_s": "0.001", "SI.hMotors.motorErrorMsg": "{\'\'}", "SI.hMotors.moveInProgress": "false", "SI.hMotors.moveTimeout_s": "10", "SI.hMotors.name": "\'SI Motors\'", "SI.hMotors.reserverInfo": "\'\'", "SI.hMotors.samplePosition": "[-5913.12 -20399.4 692.467]", "SI.hMotors.simulatedAxes": "[false false false]", "SI.hMotors.userDefinedPositions": "[]", "SI.hMotors.userInfo": "\'\'", "SI.hMotors.warnMsg": "\'\'", "SI.hPhotostim.allowMultipleOutputs": "false", "SI.hPhotostim.autoTriggerPeriod": "0", "SI.hPhotostim.compensateMotionEnabled": "true", "SI.hPhotostim.completedSequences": "0", "SI.hPhotostim.errorMsg": "\'\'", "SI.hPhotostim.laserActiveSignalAdvance": "0.001", "SI.hPhotostim.lastMotion": "[0 0]", "SI.hPhotostim.logging": "false", "SI.hPhotostim.monitoring": "false", "SI.hPhotostim.monitoringSampleRate": "9000", "SI.hPhotostim.name": "\'SI Photostim\'", "SI.hPhotostim.nextStimulus": "1", "SI.hPhotostim.numOutputs": "0", "SI.hPhotostim.numSequences": "Inf", "SI.hPhotostim.reserverInfo": "\'\'", "SI.hPhotostim.sequencePosition": "1", "SI.hPhotostim.sequenceSelectedStimuli": "[]", "SI.hPhotostim.status": "\'Offline\'", "SI.hPhotostim.stimImmediately": "false", "SI.hPhotostim.stimSelectionAssignment": "[]", "SI.hPhotostim.stimSelectionDevice": "\'\'", "SI.hPhotostim.stimSelectionTerms": "[]", "SI.hPhotostim.stimSelectionTriggerTerm": "[]", "SI.hPhotostim.stimTriggerTerm": "1", "SI.hPhotostim.stimulusMode": "\'onDemand\'", "SI.hPhotostim.syncTriggerTerm": "[]", "SI.hPhotostim.userInfo": "\'\'", "SI.hPhotostim.warnMsg": "\'\'", "SI.hPhotostim.zMode": "\'2D\'", "SI.hPmts.autoPower": "true", "SI.hPmts.autoPowerOnWaitTime_s": "0.3", "SI.hPmts.bandwidths": "8e+07", "SI.hPmts.errorMsg": "\'\'", "SI.hPmts.gains": "0.7", "SI.hPmts.name": "\'SI Pmts\'", "SI.hPmts.names": "{\'PMT2100\'}", "SI.hPmts.offsets": "0.4019", "SI.hPmts.powersOn": "true", "SI.hPmts.reserverInfo": "\'\'", "SI.hPmts.tripped": "false", "SI.hPmts.userInfo": "\'\'", "SI.hPmts.warnMsg": "\'\'", "SI.hRoiManager.errorMsg": "\'\'", "SI.hRoiManager.forceSquarePixelation": "true", "SI.hRoiManager.forceSquarePixels": "true", "SI.hRoiManager.imagingFovDeg": "[-9 -9;9 -9;9 9;-9 9]", "SI.hRoiManager.imagingFovUm": "[-135 -135;135 -135;135 135;-135 135]", "SI.hRoiManager.linePeriod": "6.31018e-05", "SI.hRoiManager.linesPerFrame": "512", "SI.hRoiManager.mroiEnable": "false", "SI.hRoiManager.name": "\'SI RoiManager\'", "SI.hRoiManager.pixelsPerLine": "512", "SI.hRoiManager.reserverInfo": "\'\'", "SI.hRoiManager.scanAngleMultiplierFast": "1", "SI.hRoiManager.scanAngleMultiplierSlow": "1", "SI.hRoiManager.scanAngleShiftFast": "0", "SI.hRoiManager.scanAngleShiftSlow": "0", "SI.hRoiManager.scanFramePeriod": "0.0333177", "SI.hRoiManager.scanFrameRate": "30.0141", "SI.hRoiManager.scanRotation": "0", "SI.hRoiManager.scanType": "\'frame\'", "SI.hRoiManager.scanVolumeRate": "0.375176", "SI.hRoiManager.scanZoomFactor": "1", "SI.hRoiManager.userInfo": "\'\'", "SI.hRoiManager.warnMsg": "\'\'", "SI.hScan2D.beamClockDelay": "1.5e-06", "SI.hScan2D.beamClockExtend": "0", "SI.hScan2D.bidirectional": "true", "SI.hScan2D.channelOffsets": "[321 -14482]", "SI.hScan2D.channels": "{}", "SI.hScan2D.channelsAdcResolution": "16", "SI.hScan2D.channelsAutoReadOffsets": "true", "SI.hScan2D.channelsAvailable": "2", "SI.hScan2D.channelsDataType": "\'int16\'", "SI.hScan2D.channelsFilter": "\'fbw\'", "SI.hScan2D.channelsInputRanges": "{[-1 1] [-1 1]}", "SI.hScan2D.channelsSubtractOffsets": "[true true]", "SI.hScan2D.customFilterClockPeriod": "2880", "SI.hScan2D.errorMsg": "\'\'", "SI.hScan2D.fillFractionSpatial": "0.9", "SI.hScan2D.fillFractionTemporal": "0.712867", "SI.hScan2D.flybackTimePerFrame": "0.001", "SI.hScan2D.flytoTimePerScanfield": "0.001", "SI.hScan2D.fovCornerPoints": "[-13 -10;13 -10;13 10;-13 10]", "SI.hScan2D.hasResonantMirror": "true", "SI.hScan2D.hasXGalvo": "true", "SI.hScan2D.isPolygonalScanner": "false", "SI.hScan2D.keepResonantScannerOn": "false", "SI.hScan2D.linePhase": "2.56e-08", "SI.hScan2D.linePhaseMode": "\'Nearest Neighbor\'", "SI.hScan2D.lineScanFdbkSamplesPerFrame": "[]", "SI.hScan2D.lineScanNumFdbkChannels": "[]", "SI.hScan2D.lineScanSamplesPerFrame": "[]", "SI.hScan2D.logAverageDisableDivide": "false", "SI.hScan2D.logAverageFactor": "8", "SI.hScan2D.logFramesPerFile": "Inf", "SI.hScan2D.logFramesPerFileLock": "false", "SI.hScan2D.logOverwriteWarn": "false", "SI.hScan2D.mask": "[12;13;12;12;12;11;12;11;11;11;11;11;11;10;11;10;10;10;11;9;10;10;10;9;10;9;10;9;9;9;9;9;9;9;9;8;9;9;8;9;8;9;8;8;9;8;8;8;8;8;8;8;8;8;8;7;8;8;7;8;8;7;8;7;8;7;8;7;7;8;7;7;7;8;7;7;7;7;7;7;7;7;7;7;7;7;7;7;6;7;7;7;6;7;7;7;6;7;6;7;7;6;7;6;7;6;7;6;7;6;7;6;6;7;6;6;7;6;6;7;6;6;7;6;6;6;6;7;6;6;6;6;6;6;6;7;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;5;6;6;6;6;6;6;6;5;6;6;6;6;6;5;6;6;6;6;5;6;6;6;5;6;6;6;5;6;6;5;6;6;6;5;6;6;5;6;6;5;6;5;6;6;5;6;6;5;6;6;5;6;5;6;6;5;6;5;6;5;6;6;5;6;5;6;5;6;6;5;6;5;6;5;6;5;6;5;6;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;5;6;6;5;6;5;6;5;6;5;6;5;6;6;5;6;5;6;5;6;6;5;6;5;6;5;6;6;5;6;5;6;6;5;6;6;5;6;6;5;6;5;6;6;5;6;6;5;6;6;6;5;6;6;5;6;6;6;5;6;6;6;5;6;6;6;6;5;6;6;6;6;6;5;6;6;6;6;6;6;6;5;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;6;7;6;6;6;6;6;6;6;7;6;6;6;6;7;6;6;7;6;6;7;6;6;7;6;6;7;6;7;6;7;6;7;6;7;6;7;7;6;7;6;7;7;7;6;7;7;7;6;7;7;7;7;7;7;7;7;7;7;7;7;7;7;8;7;7;7;8;7;7;8;7;8;7;8;7;8;8;7;8;8;7;8;8;8;8;8;8;8;8;8;8;9;8;8;9;8;9;8;9;9;8;9;9;9;9;9;9;9;9;10;9;10;9;10;10;10;9;11;10;10;10;11;10;11;11;11;11;11;11;12;11;12;12;12;13;12]", "SI.hScan2D.maxSampleRate": "2.5e+09", "SI.hScan2D.name": "\'Imaging_RGG\'", "SI.hScan2D.nominalFovCornerPoints": "[-13 -10;13 -10;13 10;-13 10]", "SI.hScan2D.parkSlmForAcquisition": "true", "SI.hScan2D.photonDiscriminatorDifferentiateWidths": "[4 4]", "SI.hScan2D.photonDiscriminatorModes": "{\'threshold crossing\' \'threshold crossing\'}", "SI.hScan2D.photonDiscriminatorThresholds": "[1000 500]", "SI.hScan2D.physicalChannelsAvailable": "2", "SI.hScan2D.pixelBinFactor": "1", "SI.hScan2D.recordScannerFeedback": "false", "SI.hScan2D.reserverInfo": "\'\'", "SI.hScan2D.sampleRate": "2.5e+09", "SI.hScan2D.sampleRateCtl": "1e+06", "SI.hScan2D.sampleRateFdbk": "1e+06", "SI.hScan2D.scanMode": "\'resonant\'", "SI.hScan2D.scanPixelTimeMaxMinRatio": "2.6", "SI.hScan2D.scanPixelTimeMean": "8.785e-08", "SI.hScan2D.scannerFrequency": "7923.71", "SI.hScan2D.scannerToRefTransform": "[1 0 0;0 1 0;0 0 1]", "SI.hScan2D.scannerType": "\'RGG\'", "SI.hScan2D.settleTimeFraction": "0", "SI.hScan2D.simulated": "false", "SI.hScan2D.stripingEnable": "false", "SI.hScan2D.stripingPeriod": "0.1", "SI.hScan2D.trigAcqEdge": "\'rising\'", "SI.hScan2D.trigAcqInTerm": "\'\'", "SI.hScan2D.trigNextEdge": "\'rising\'", "SI.hScan2D.trigNextInTerm": "\'\'", "SI.hScan2D.trigNextStopEnable": "true", "SI.hScan2D.trigStopEdge": "\'rising\'", "SI.hScan2D.trigStopInTerm": "\'\'", "SI.hScan2D.uniformSampling": "false", "SI.hScan2D.useCustomFilterClock": "false", "SI.hScan2D.userInfo": "\'\'", "SI.hScan2D.virtualChannelSettings__1.source": "\'AI1\'", "SI.hScan2D.virtualChannelSettings__1.mode": "\'analog\'", "SI.hScan2D.virtualChannelSettings__1.threshold": "false", "SI.hScan2D.virtualChannelSettings__1.binarize": "false", "SI.hScan2D.virtualChannelSettings__1.edgeDetect": "false", "SI.hScan2D.virtualChannelSettings__1.laserGate": "false", "SI.hScan2D.virtualChannelSettings__1.disableDivide": "false", "SI.hScan2D.virtualChannelSettings__1.thresholdValue": "100", "SI.hScan2D.virtualChannelSettings__1.laserFilterWindow": "[25 25]", "SI.hScan2D.virtualChannelSettings__2.source": "\'AI1\'", "SI.hScan2D.virtualChannelSettings__2.mode": "\'analog\'", "SI.hScan2D.virtualChannelSettings__2.threshold": "false", "SI.hScan2D.virtualChannelSettings__2.binarize": "false", "SI.hScan2D.virtualChannelSettings__2.edgeDetect": "false", "SI.hScan2D.virtualChannelSettings__2.laserGate": "false", "SI.hScan2D.virtualChannelSettings__2.disableDivide": "false", "SI.hScan2D.virtualChannelSettings__2.thresholdValue": "100", "SI.hScan2D.virtualChannelSettings__2.laserFilterWindow": "[0 1]", "SI.hScan2D.warnMsg": "\'\'", "SI.hShutters.errorMsg": "\'\'", "SI.hShutters.name": "\'SI Shutters\'", "SI.hShutters.reserverInfo": "\'\'", "SI.hShutters.userInfo": "\'\'", "SI.hShutters.warnMsg": "\'\'", "SI.hStackManager.actualNumSlices": "10", "SI.hStackManager.actualNumVolumes": "2", "SI.hStackManager.actualStackZStepSize": "18.892", "SI.hStackManager.arbitraryZs": "[0;1]", "SI.hStackManager.boundedStackDefinition": "\'numSlices\'", "SI.hStackManager.centeredStack": "1", "SI.hStackManager.closeShutterBetweenSlices": "false", "SI.hStackManager.enable": "true", "SI.hStackManager.errorMsg": "\'\'", "SI.hStackManager.framesPerSlice": "8", "SI.hStackManager.name": "\'SI StackManager\'", "SI.hStackManager.numFastZActuators": "1", "SI.hStackManager.numFramesPerVolume": "80", "SI.hStackManager.numFramesPerVolumeWithFlyback": "80", "SI.hStackManager.numSlices": "10", "SI.hStackManager.numVolumes": "2", "SI.hStackManager.reserverInfo": "\'\'", "SI.hStackManager.stackActuator": "\'motor\'", "SI.hStackManager.stackDefinition": "\'bounded\'", "SI.hStackManager.stackEndPowerFraction": "0.92", "SI.hStackManager.stackFastWaveformType": "\'sawtooth\'", "SI.hStackManager.stackMode": "\'slow\'", "SI.hStackManager.stackReturnHome": "true", "SI.hStackManager.stackStartPowerFraction": "0.92", "SI.hStackManager.stackZEndPos": "912.489", "SI.hStackManager.stackZStartPos": "742.467", "SI.hStackManager.stackZStepSize": "1", "SI.hStackManager.useStartEndPowers": "1", "SI.hStackManager.userInfo": "\'\'", "SI.hStackManager.warnMsg": "\'\'", "SI.hStackManager.zPowerReference": "742.467", "SI.hStackManager.zs": "[742.467 742.467 742.467 742.467 742.467 742.467 742.467 742.467 761.359 761.359 761.359 761.359 761.359 761.359 761.359 761.359 780.25 780.25 780.25 780.25 780.25 780.25 780.25 780.25 799.141 799.141 799.141 799.141 799.141 799.141 799.141 799.141 818.032 818.032 818.032 818.032 818.032 818.032 818.032 818.032 836.924 836.924 836.924 836.924 836.924 836.924 836.924 836.924 855.815 855.815 855.815 855.815 855.815 855.815 855.815 855.815 874.706 874.706 874.706 874.706 874.706 874.706 874.706 874.706 893.597 893.597 893.597 893.597 893.597 893.597 893.597 893.597 912.489 912.489 912.489 912.489 912.489 912.489 912.489 912.489]", "SI.hStackManager.zsAllActuators": "[742.467;742.467;742.467;742.467;742.467;742.467;742.467;742.467;761.359;761.359;761.359;761.359;761.359;761.359;761.359;761.359;780.25;780.25;780.25;780.25;780.25;780.25;780.25;780.25;799.141;799.141;799.141;799.141;799.141;799.141;799.141;799.141;818.032;818.032;818.032;818.032;818.032;818.032;818.032;818.032;836.924;836.924;836.924;836.924;836.924;836.924;836.924;836.924;855.815;855.815;855.815;855.815;855.815;855.815;855.815;855.815;874.706;874.706;874.706;874.706;874.706;874.706;874.706;874.706;893.597;893.597;893.597;893.597;893.597;893.597;893.597;893.597;912.489;912.489;912.489;912.489;912.489;912.489;912.489;912.489]", "SI.hStackManager.zsRelative": "[50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50;50]", "SI.hTileManager.acqDoneFlag": "false", "SI.hTileManager.errorMsg": "\'\'", "SI.hTileManager.isFastZ": "false", "SI.hTileManager.loopedAcquisition": "false", "SI.hTileManager.name": "\'SI TileManager\'", "SI.hTileManager.reserverInfo": "\'\'", "SI.hTileManager.scanAbortFlag": "false", "SI.hTileManager.scanFramesPerTile": "1", "SI.hTileManager.scanStageSettleTime": "0.1", "SI.hTileManager.scanTileSortFcn": "\'scanimage.components.tileTools.tileSortingFcns.naiveNearest\'", "SI.hTileManager.tileScanIndices": "[]", "SI.hTileManager.tileScanningInProgress": "false", "SI.hTileManager.tilesDone": "[]", "SI.hTileManager.userInfo": "\'\'", "SI.hTileManager.warnMsg": "\'\'", "SI.hUserFunctions.errorMsg": "\'\'", "SI.hUserFunctions.name": "\'SI UserFunctions\'", "SI.hUserFunctions.reserverInfo": "\'\'", "SI.hUserFunctions.userFunctionsCfg": "[]", "SI.hUserFunctions.userFunctionsUsr": "[]", "SI.hUserFunctions.userInfo": "\'\'", "SI.hUserFunctions.warnMsg": "\'\'", "SI.hWSConnector.communicationTimeout": "5", "SI.hWSConnector.enable": "false", "SI.hWSConnector.errorMsg": "\'\'", "SI.hWSConnector.name": "\'SI WSConnector\'", "SI.hWSConnector.reserverInfo": "\'\'", "SI.hWSConnector.userInfo": "\'\'", "SI.hWSConnector.warnMsg": "\'\'", "SI.hWaveformManager.errorMsg": "\'\'", "SI.hWaveformManager.name": "\'SI WaveformManager\'", "SI.hWaveformManager.optimizedScanners": "{}", "SI.hWaveformManager.reserverInfo": "\'\'", "SI.hWaveformManager.userInfo": "\'\'", "SI.hWaveformManager.warnMsg": "\'\'", "SI.imagingSystem": "\'Imaging_RGG\'", "SI.loopAcqInterval": "10", "SI.name": "\'ScanImage\'", "SI.objectiveResolution": "15", "SI.reserverInfo": "\'\'", "SI.shutDownScript": "\'\'", "SI.startUpScript": "\'\'", "SI.userInfo": "\'\'", "SI.warnMsg": "\'\'"}'
        )


class TestHdf5ImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = Hdf5ImagingInterface
    interface_kwargs = dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "hdf5" / "demoMovie.hdf5"))
    save_directory = OUTPUT_PATH


class TestSbxImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = SbxImagingInterface
    interface_kwargs = [
        dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / f"sample.mat")),
        dict(file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / f"sample.sbx")),
    ]
    save_directory = OUTPUT_PATH


class TestBrukerTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = BrukerTiffImagingInterface
    interface_kwargs = dict(
        folder_path=str(
            OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
        )
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
        cls.device_metadata = dict(name="BrukerFluorescenceMicroscope", description="Version 5.6.64.400")
        cls.optical_channel_metadata = dict(
            name="Ch2",
            emission_lambda=np.NAN,
            description="An optical channel of the microscope.",
        )
        cls.imaging_plane_metadata = dict(
            name="ImagingPlane",
            description="The plane imaged at 5e-06 meters depth.",
            excitation_lambda=np.NAN,
            indicator="unknown",
            location="unknown",
            device=cls.device_metadata["name"],
            optical_channel=[cls.optical_channel_metadata],
            imaging_rate=30.345939461428763,
            grid_spacing=[1.1078125e-06, 1.1078125e-06],
        )

        cls.two_photon_series_metadata = dict(
            name="TwoPhotonSeries",
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            unit="px",
            dimension=[512, 512],
            imaging_plane=cls.imaging_plane_metadata["name"],
            format="tiff",
            scan_line_rate=15840.580398865815,
            field_of_view=[0.0005672, 0.0005672, 5e-06],
        )

        cls.ophys_metadata = dict(
            Device=[cls.device_metadata],
            ImagingPlane=[cls.imaging_plane_metadata],
            TwoPhotonSeries=[cls.two_photon_series_metadata],
        )

    def check_extracted_metadata(self, metadata: dict):
        self.assertEqual(metadata["NWBFile"]["session_start_time"], datetime(2023, 2, 20, 15, 58, 25))
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            self.assertIn(self.device_metadata["name"], nwbfile.devices)
            self.assertEqual(
                nwbfile.devices[self.device_metadata["name"]].description, self.device_metadata["description"]
            )
            self.assertIn(self.imaging_plane_metadata["name"], nwbfile.imaging_planes)
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            self.assertEqual(optical_channel.name, self.optical_channel_metadata["name"])
            self.assertEqual(optical_channel.description, self.optical_channel_metadata["description"])
            self.assertEqual(imaging_plane.description, self.imaging_plane_metadata["description"])
            self.assertEqual(imaging_plane.imaging_rate, self.imaging_plane_metadata["imaging_rate"])
            assert_array_equal(imaging_plane.grid_spacing[:], self.imaging_plane_metadata["grid_spacing"])
            self.assertIn(self.two_photon_series_metadata["name"], nwbfile.acquisition)
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            self.assertEqual(two_photon_series.description, self.two_photon_series_metadata["description"])
            self.assertEqual(two_photon_series.unit, self.two_photon_series_metadata["unit"])
            self.assertEqual(two_photon_series.format, self.two_photon_series_metadata["format"])
            self.assertEqual(two_photon_series.scan_line_rate, self.two_photon_series_metadata["scan_line_rate"])
            assert_array_equal(two_photon_series.field_of_view[:], self.two_photon_series_metadata["field_of_view"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)


class TestMicroManagerTiffImagingInterface(ImagingExtractorInterfaceTestMixin, TestCase):
    data_interface_cls = MicroManagerTiffImagingInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "MicroManagerTif" / "TS12_20220407_20hz_noteasy_1")
    )
    save_directory = OUTPUT_PATH

    @classmethod
    def setUpClass(cls) -> None:
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
        self.assertEqual(
            metadata["NWBFile"]["session_start_time"],
            datetime(2022, 4, 7, 15, 6, 56, 842000, tzinfo=tzoffset(None, -18000)),
        )
        self.assertDictEqual(metadata["Ophys"], self.ophys_metadata)

    def check_read_nwb(self, nwbfile_path: str):
        """Check the ophys metadata made it to the NWB file"""

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            self.assertIn(self.imaging_plane_metadata["name"], nwbfile.imaging_planes)
            imaging_plane = nwbfile.imaging_planes[self.imaging_plane_metadata["name"]]
            optical_channel = imaging_plane.optical_channel[0]
            self.assertEqual(optical_channel.name, self.optical_channel_metadata["name"])
            self.assertEqual(optical_channel.description, self.optical_channel_metadata["description"])
            self.assertEqual(imaging_plane.description, self.imaging_plane_metadata["description"])
            self.assertEqual(imaging_plane.imaging_rate, self.imaging_plane_metadata["imaging_rate"])
            self.assertIn(self.two_photon_series_metadata["name"], nwbfile.acquisition)
            two_photon_series = nwbfile.acquisition[self.two_photon_series_metadata["name"]]
            self.assertEqual(two_photon_series.description, self.two_photon_series_metadata["description"])
            self.assertEqual(two_photon_series.unit, self.two_photon_series_metadata["unit"])
            self.assertEqual(two_photon_series.format, self.two_photon_series_metadata["format"])
            assert_array_equal(two_photon_series.dimension[:], self.two_photon_series_metadata["dimension"])

        super().check_read_nwb(nwbfile_path=nwbfile_path)
