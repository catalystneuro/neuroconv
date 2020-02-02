import nwbn_conversion_tools.gui.classes as groups_modules

# This carries the reference mapping between pynwb groups names and their
# respective GUI forms constructing classes.
# It can be updated by extensions at the __init__ of nwbn_conversion_gui.py
name_class_reference = {
    'Device': groups_modules.forms_general.GroupDevice,
    # Ophys
    'OpticalChannel': groups_modules.forms_ophys.GroupOpticalChannel,
    'ImagingPlane': groups_modules.forms_ophys.GroupImagingPlane,
    'TwoPhotonSeries': groups_modules.forms_ophys.GroupTwoPhotonSeries,
    'CorrectedImageStack': groups_modules.forms_ophys.GroupCorrectedImageStack,
    'MotionCorrection': groups_modules.forms_ophys.GroupMotionCorrection,
    'PlaneSegmentation': groups_modules.forms_ophys.GroupPlaneSegmentation,
    'ImageSegmentation': groups_modules.forms_ophys.GroupImageSegmentation,
    'RoiResponseSeries': groups_modules.forms_ophys.GroupRoiResponseSeries,
    'DfOverF': groups_modules.forms_ophys.GroupDfOverF,
    'Fluorescence': groups_modules.forms_ophys.GroupFluorescence,
    'GrayscaleVolume': groups_modules.forms_ophys.GroupGrayscaleVolume,
    # Ecephys
    'ElectrodeGroup': groups_modules.forms_ecephys.GroupElectrodeGroup,
    'ElectricalSeries': groups_modules.forms_ecephys.GroupElectricalSeries,
    'SpikeEventSeries': groups_modules.forms_ecephys.GroupSpikeEventSeries,
    'EventDetection': groups_modules.forms_ecephys.GroupEventDetection,
    'EventWaveform': groups_modules.forms_ecephys.GroupEventWaveform,
    'LFP': groups_modules.forms_ecephys.GroupLFP,
    'FilteredEphys': groups_modules.forms_ecephys.GroupFilteredEphys,
    'FeatureExtraction': groups_modules.forms_ecephys.GroupFeatureExtraction,
    # Behavior
    'SpatialSeries': groups_modules.forms_behavior.GroupSpatialSeries,
    'BehavioralEpochs': groups_modules.forms_behavior.GroupBehavioralEpochs,
    'BehavioralEvents': groups_modules.forms_behavior.GroupBehavioralEvents,
    'BehavioralTimeSeries': groups_modules.forms_behavior.GroupBehavioralTimeSeries,
    'PupilTracking': groups_modules.forms_behavior.GroupPupilTracking,
    'EyeTracking': groups_modules.forms_behavior.GroupEyeTracking,
    'CompassDirection': groups_modules.forms_behavior.GroupCompassDirection,
    'Position': groups_modules.forms_behavior.GroupPosition,
}
