import nwbn_conversion_tools.gui.classes as gui_modules
import pynwb


# This carries the reference mapping between pynwb groups names and their
# respective GUI forms constructing classes.
# It can be updated by extensions at the __init__ of nwbn_conversion_gui.py
name_to_gui_class = {
    'Device': gui_modules.forms_general.GroupDevice,
    # Ophys
    'OpticalChannel': gui_modules.forms_ophys.GroupOpticalChannel,
    'ImagingPlane': gui_modules.forms_ophys.GroupImagingPlane,
    'TwoPhotonSeries': gui_modules.forms_ophys.GroupTwoPhotonSeries,
    'CorrectedImageStack': gui_modules.forms_ophys.GroupCorrectedImageStack,
    'MotionCorrection': gui_modules.forms_ophys.GroupMotionCorrection,
    'PlaneSegmentation': gui_modules.forms_ophys.GroupPlaneSegmentation,
    'ImageSegmentation': gui_modules.forms_ophys.GroupImageSegmentation,
    'RoiResponseSeries': gui_modules.forms_ophys.GroupRoiResponseSeries,
    'DfOverF': gui_modules.forms_ophys.GroupDfOverF,
    'Fluorescence': gui_modules.forms_ophys.GroupFluorescence,
    'GrayscaleVolume': gui_modules.forms_ophys.GroupGrayscaleVolume,
    # Ecephys
    'ElectrodeGroup': gui_modules.forms_ecephys.GroupElectrodeGroup,
    'ElectricalSeries': gui_modules.forms_ecephys.GroupElectricalSeries,
    'SpikeEventSeries': gui_modules.forms_ecephys.GroupSpikeEventSeries,
    'EventDetection': gui_modules.forms_ecephys.GroupEventDetection,
    'EventWaveform': gui_modules.forms_ecephys.GroupEventWaveform,
    'LFP': gui_modules.forms_ecephys.GroupLFP,
    'FilteredEphys': gui_modules.forms_ecephys.GroupFilteredEphys,
    'FeatureExtraction': gui_modules.forms_ecephys.GroupFeatureExtraction,
    # Behavior
    'SpatialSeries': gui_modules.forms_behavior.GroupSpatialSeries,
    'BehavioralEpochs': gui_modules.forms_behavior.GroupBehavioralEpochs,
    'BehavioralEvents': gui_modules.forms_behavior.GroupBehavioralEvents,
    'BehavioralTimeSeries': gui_modules.forms_behavior.GroupBehavioralTimeSeries,
    'PupilTracking': gui_modules.forms_behavior.GroupPupilTracking,
    'EyeTracking': gui_modules.forms_behavior.GroupEyeTracking,
    'CompassDirection': gui_modules.forms_behavior.GroupCompassDirection,
    'Position': gui_modules.forms_behavior.GroupPosition,
}

# This carries the reference mapping between pynwb groups names and their
# respective pynwb classes.
# It can be updated by extensions at the __init__ of nwbn_conversion_gui.py
name_to_pynwb_class = {
    'Device': pynwb.device.Device,
    # Ophys
    'OpticalChannel': pynwb.ophys.OpticalChannel,
    'ImagingPlane': pynwb.ophys.ImagingPlane,
    'TwoPhotonSeries': pynwb.ophys.TwoPhotonSeries,
    'CorrectedImageStack': pynwb.ophys.CorrectedImageStack,
    'MotionCorrection': pynwb.ophys.MotionCorrection,
    'PlaneSegmentation': pynwb.ophys.PlaneSegmentation,
    'ImageSegmentation': pynwb.ophys.ImageSegmentation,
    'RoiResponseSeries': pynwb.ophys.RoiResponseSeries,
    'DfOverF': pynwb.ophys.DfOverF,
    'Fluorescence': pynwb.ophys.Fluorescence,
    # Ecephys
    'ElectrodeGroup': pynwb.ecephys.ElectrodeGroup,
    'ElectricalSeries': pynwb.ecephys.ElectricalSeries,
    'SpikeEventSeries': pynwb.ecephys.SpikeEventSeries,
    'EventDetection': pynwb.ecephys.EventDetection,
    'EventWaveform': pynwb.ecephys.EventWaveform,
    'LFP': pynwb.ecephys.LFP,
    'FilteredEphys': pynwb.ecephys.FilteredEphys,
    'FeatureExtraction': pynwb.ecephys.FeatureExtraction,
    # Behavior
    'SpatialSeries': pynwb.behavior.SpatialSeries,
    'BehavioralEpochs': pynwb.behavior.BehavioralEpochs,
    'BehavioralEvents': pynwb.behavior.BehavioralEvents,
    'BehavioralTimeSeries': pynwb.behavior.BehavioralTimeSeries,
    'PupilTracking': pynwb.behavior.PupilTracking,
    'EyeTracking': pynwb.behavior.EyeTracking,
    'CompassDirection': pynwb.behavior.CompassDirection,
    'Position': pynwb.behavior.Position,
}
