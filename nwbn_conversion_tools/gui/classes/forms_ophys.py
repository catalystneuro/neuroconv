from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QComboBox,
    QCheckBox, QFileDialog, QStyle)
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from datetime import datetime
import numpy as np
import yaml
import os



class GroupOpticalChannel(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.OpticalChannel fields filling form."""
        super().__init__()
        self.setTitle('OpticalChannel')
        self.parent = parent
        self.group_name = 'OpticalChannel'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('OpticalChannel')
        self.lin_name.setToolTip("the name of this optical channel")
        nOptCh = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupOpticalChannel):
                nOptCh += 1
        if nOptCh > 0:
            self.lin_name.setText('OpticalChannel'+str(nOptCh))

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('description')
        self.lin_description.setToolTip("Any notes or comments about the channel")

        self.lbl_emission_lambda = QLabel('emission_lambda:')
        self.lin_emission_lambda = QLineEdit('0.0')
        self.lin_emission_lambda.setToolTip("Emission lambda for channel")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_emission_lambda, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_emission_lambda, 2, 2, 1, 4)

        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['description'] = self.lin_description.text()
        try:
            data['emission_lambda'] = float(self.lin_emission_lambda.text())
        except:
            data['emission_lambda'] = 0.0
            print("'emission_lambda' must be a float")
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_description.setText(data['description'])
        self.lin_emission_lambda.setText(str(data['emission_lambda']))



class GroupImagingPlane(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.ImagingPlane fields filling form."""
        super().__init__()
        self.setTitle('ImagingPlane')
        self.parent = parent
        self.group_name = 'ImagingPlane'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('ImagingPlane')
        self.lin_name.setToolTip("The name of this ImagingPlane")
        nImPl = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupImagingPlane):
                nImPl += 1
        if nImPl > 0:
            self.lin_name.setText('ImagingPlane'+str(nImPl))

        self.lbl_optical_channel = QLabel('optical_channel:')
        self.combo_optical_channel = QComboBox()
        self.combo_optical_channel.setToolTip("One of possibly many groups storing "
            "channelspecific data")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('description')
        self.lin_description.setToolTip("Description of this ImagingPlane")

        self.lbl_device = QLabel('device:')
        self.combo_device = QComboBox()
        self.combo_device.setToolTip("The device that was used to record")

        self.lbl_excitation_lambda = QLabel('excitation_lambda:')
        self.lin_excitation_lambda = QLineEdit('0.0')
        self.lin_excitation_lambda.setToolTip("Excitation wavelength in nm")

        self.lbl_imaging_rate = QLabel('imaging_rate:')
        self.lin_imaging_rate = QLineEdit('0.0')
        self.lin_imaging_rate.setToolTip("Rate images are acquired, in Hz")

        self.lbl_indicator = QLabel('indicator:')
        self.lin_indicator = QLineEdit('indicator')
        self.lin_indicator.setToolTip("Calcium indicator")

        self.lbl_location = QLabel('location:')
        self.lin_location = QLineEdit('location')
        self.lin_location.setToolTip("Location of image plane")

        self.lbl_manifold = QLabel('manifold:')
        self.chk_manifold = QCheckBox("Get from source file")
        self.chk_manifold.setChecked(False)
        self.chk_manifold.setToolTip("Physical position of each pixel. size=(height, "
            "width, xyz).\n Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1")
        self.lin_conversion.setToolTip("Multiplier to get from stored values to "
            "specified unit (e.g., 1e-3 for millimeters)")

        self.lbl_unit = QLabel('unit:')
        self.lin_unit = QLineEdit('')
        self.lin_unit.setPlaceholderText("meters")
        self.lin_unit.setToolTip("Base unit that coordinates are stored in (e.g., Meters)")

        self.lbl_reference_frame = QLabel('reference_frame:')
        self.lin_reference_frame = QLineEdit('')
        self.lin_reference_frame.setPlaceholderText("reference_frame")
        self.lin_reference_frame.setToolTip("Describes position and reference frame "
            "of manifold based on position of first element in manifold.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_optical_channel, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_optical_channel, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_device, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_device, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_excitation_lambda, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_excitation_lambda, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_rate, 5, 0, 1, 2)
        self.grid.addWidget(self.lin_imaging_rate, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_indicator, 6, 0, 1, 2)
        self.grid.addWidget(self.lin_indicator, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_location, 7, 0, 1, 2)
        self.grid.addWidget(self.lin_location, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_manifold, 8, 0, 1, 2)
        self.grid.addWidget(self.chk_manifold, 8, 2, 1, 2)
        self.grid.addWidget(self.lbl_conversion, 9, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_unit, 10, 0, 1, 2)
        self.grid.addWidget(self.lin_unit, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_reference_frame, 11, 0, 1, 2)
        self.grid.addWidget(self.lin_reference_frame, 11, 2, 1, 4)

        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_optical_channel.clear()
        self.combo_device.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupOpticalChannel):
                self.combo_optical_channel.addItem(grp.lin_name.text())
            if isinstance(grp, GroupDevice):
                self.combo_device.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['optical_channel'] = str(self.combo_optical_channel.currentText())
        data['description'] = self.lin_description.text()
        data['device'] = str(self.combo_device.currentText())
        try:
            data['excitation_lambda'] = float(self.lin_excitation_lambda.text())
        except:
            data['excitation_lambda'] = 0.0
        try:
            data['imaging_rate'] = float(self.lin_imaging_rate.text())
        except:
            data['imaging_rate'] = 0.0
        data['indicator'] = self.lin_indicator.text()
        data['location'] = self.lin_location.text()
        if self.chk_manifold.isChecked():
            data['manifold'] = True
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except:
            data['conversion'] = 0.0
        data['unit'] = self.lin_unit.text()
        data['reference_frame'] = self.lin_reference_frame.text()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_optical_channel.clear()
        self.combo_optical_channel.addItem(data['optical_channel'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        self.combo_device.clear()
        self.combo_device.addItem(data['device'])
        self.lin_excitation_lambda.setText(str(data['excitation_lambda']))
        self.lin_imaging_rate.setText(str(data['imaging_rate']))
        self.lin_indicator.setText(str(data['indicator']))
        self.lin_location.setText(str(data['location']))
        if 'manifold' in data:
            self.chk_manifold.setChecked(True)
        if 'conversion' in data:
            self.lin_conversion.setText(str(data['conversion']))
        if 'unit' in data:
            self.lin_unit.setText(data['unit'])
        if 'reference_frame' in data:
            self.lin_reference_frame.setText(data['reference_frame'])



class GroupTwoPhotonSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.TwoPhotonSeries fields filling form."""
        super().__init__()
        self.setTitle('TwoPhotonSeries')
        self.parent = parent
        self.group_name = 'TwoPhotonSeries'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('TwoPhotonSeries')
        self.lin_name.setToolTip("The name of this TimeSeries dataset")
        nTPS = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupTwoPhotonSeries):
                nTPS += 1
        if nTPS > 0:
            self.lin_name.setText('TwoPhotonSeries'+str(nTPS))

        self.lbl_imaging_plane = QLabel('imaging_plane:')
        self.combo_imaging_plane = QComboBox()
        self.combo_imaging_plane.setToolTip("Imaging plane class/pointer")

        self.lbl_data = QLabel('data:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(False)
        self.chk_data.setToolTip("The data this TimeSeries dataset stores.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_unit = QLabel('unit:')
        self.lin_unit = QLineEdit('')
        self.lin_unit.setPlaceholderText("unit")
        self.lin_unit.setToolTip("The base unit of measurement (should be SI unit)")

        self.lbl_format = QLabel("format:")
        self.lin_format = QLineEdit("")
        self.lin_format.setPlaceholderText("format")
        self.lin_format.setToolTip("Format of image. Three types: 1) Image format: "
            "tiff, png, jpg, etc. 2) external 3) raw")

        self.lbl_field_of_view = QLabel("field_of_view:")
        self.chk_field_of_view = QCheckBox("Get from source file")
        self.chk_field_of_view.setChecked(False)
        self.chk_field_of_view.setToolTip("Width, height and depth of image, or imaged"
            " area (meters).\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_pmt_gain = QLabel("pmt_gain:")
        self.lin_pmt_gain = QLineEdit("")
        self.lin_pmt_gain.setPlaceholderText("1.0")
        self.lin_pmt_gain.setToolTip("Photomultiplier gain")

        self.lbl_scan_line_rate = QLabel("scan_line_rate:")
        self.lin_scan_line_rate = QLineEdit("")
        self.lin_scan_line_rate.setPlaceholderText("0.0")
        self.lin_scan_line_rate.setToolTip("Lines imaged per second")

        self.lbl_external_file = QLabel("external_file:")
        self.lin_external_file = QLineEdit("")
        self.lin_external_file.setPlaceholderText("path/to/external_file")
        self.lin_external_file.setToolTip("Path or URL to one or more external file(s). "
        "Field only present if format=external. Either external_file or data must "
        "be specified, but not both.")

        self.lbl_starting_frame = QLabel("starting_frame:")
        self.chk_starting_frame = QCheckBox("Get from source file")
        self.chk_starting_frame.setChecked(False)
        self.chk_starting_frame.setToolTip("Each entry is the frame number in the "
            "corresponding external_file variable. This serves as an index to what frames "
            "each file contains.\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_bits_per_pixel = QLabel("bits_per_pixel:")
        self.lin_bits_per_pixel = QLineEdit("")
        self.lin_bits_per_pixel.setPlaceholderText("1")
        self.lin_bits_per_pixel.setToolTip("Number of bit per image pixel")

        self.lbl_dimension = QLabel("dimension:")
        self.lin_dimension = QLineEdit("")
        self.lin_dimension.setPlaceholderText("1,1,1")
        self.lin_dimension.setToolTip("Number of pixels on x, y, (and z) axes")

        self.lbl_resolution = QLabel("resolution:")
        self.lin_resolution = QLineEdit("")
        self.lin_resolution.setPlaceholderText("0.0")
        self.lin_resolution.setToolTip("The smallest meaningful difference (in "
            "specified unit) between values in data")

        self.lbl_conversion = QLabel("conversion:")
        self.lin_conversion = QLineEdit("")
        self.lin_conversion.setPlaceholderText("0.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to "
            "convert to volts")

        self.lbl_timestamps = QLabel("timestamps:")
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip("Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_starting_time = QLabel("starting_time:")
        self.chk_starting_time = QCheckBox("Get from source file")
        self.chk_starting_time.setChecked(False)
        self.chk_starting_time.setToolTip("The timestamp of the first sample.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_rate = QLabel("rate:")
        self.chk_rate = QCheckBox("Get from source file")
        self.chk_rate.setChecked(False)
        self.chk_rate.setToolTip("Sampling rate in Hz.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_comments = QLabel("comments:")
        self.lin_comments = QLineEdit("")
        self.lin_comments.setPlaceholderText("comments")
        self.lin_comments.setToolTip("Human-readable comments about this TimeSeries dataset")

        self.lbl_description = QLabel("description:")
        self.lin_description = QLineEdit("")
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip("Description of this TimeSeries dataset")

        self.lbl_control = QLabel("control:")
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip("Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_control_description = QLabel("control_description:")
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip("Description of each control value.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_plane, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_imaging_plane, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 2, 2, 1, 2)
        self.grid.addWidget(self.lbl_unit, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_unit, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_format, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_format, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_field_of_view, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_field_of_view, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_pmt_gain, 6, 0, 1, 2)
        self.grid.addWidget(self.lin_pmt_gain, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_scan_line_rate, 7, 0, 1, 2)
        self.grid.addWidget(self.lin_scan_line_rate, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_external_file, 8, 0, 1, 2)
        self.grid.addWidget(self.lin_external_file, 8, 2, 1, 4)
        self.grid.addWidget(self.lbl_starting_frame, 9, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_frame, 9, 2, 1, 2)
        self.grid.addWidget(self.lbl_bits_per_pixel, 10, 0, 1, 2)
        self.grid.addWidget(self.lin_bits_per_pixel, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_dimension, 11, 0, 1, 2)
        self.grid.addWidget(self.lin_dimension, 11, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 12, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 12, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 13, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 13, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 14, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 14, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 15, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_time, 15, 2, 1, 2)
        self.grid.addWidget(self.lbl_rate, 16, 0, 1, 2)
        self.grid.addWidget(self.chk_rate, 16, 2, 1, 2)
        self.grid.addWidget(self.lbl_comments, 17, 0, 1, 2)
        self.grid.addWidget(self.lin_comments, 17, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 18, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 18, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 19, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 19, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 20, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 20, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_imaging_plane.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupImagingPlane):
                self.combo_imaging_plane.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['imaging_plane'] = self.combo_imaging_plane.currentText()
        if self.chk_data.isChecked():
            data['data'] = True
        data['unit'] = self.lin_unit.text()
        data['format'] = self.lin_format.text()
        if self.chk_field_of_view.isChecked():
            data['field_of_view'] = True
        try:
            data['pmt_gain'] = float(self.lin_pmt_gain.text())
        except:
            pass
        try:
            data['scan_line_rate'] = float(self.lin_scan_line_rate.text())
        except:
            pass
        if self.lin_format.text()=='external':
            data['external_file'] = self.lin_external_file.text()
            if self.chk_starting_frame.isChecked():
                data['starting_frame'] = True
        try:
            data['bits_per_pixel'] = int(self.lin_bits_per_pixel.text())
        except:
            pass
        try:
            data['dimension'] = [int(it) for it in self.lin_dimension.text().split(',')]
        except:
            pass
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except:
            pass
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except:
            pass
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        if self.chk_starting_time.isChecked():
            data['starting_time'] = True
        if self.chk_rate.isChecked():
            data['rate'] = True
        data['comments'] = self.lin_comments.text()
        data['description'] = self.lin_description.text()
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_imaging_plane.clear()
        self.combo_imaging_plane.addItem(data['imaging_plane'])
        if 'data' in data:
            self.chk_data.setChecked(True)
        if 'unit' in data:
            self.lin_unit.setText(data['unit'])
        if 'format' in data:
            self.lin_format.setText(data['format'])
        if 'field_of_view' in data:
            self.chk_field_of_view.setChecked(True)
        if 'pmt_gain' in data:
            self.lin_pmt_gain.setText(str(data['pmt_gain']))
        if 'scan_line_rate' in data:
            self.lin_scan_line_rate.setText(str(data['scan_line_rate']))
        if 'external_file' in data:
            self.lin_format.setText('external')
            self.lin_external_file.setText(data['external_file'])
            self.chk_starting_frame.setChecked(False)
        else:
            self.lin_format.setText('')
            self.lin_external_file.setText('')
            self.chk_starting_frame.setChecked(True)
        if 'bits_per_pixel' in data:
            self.lin_bits_per_pixel.setText(str(data['bits_per_pixel']))
        if 'dimension' in data:
            self.lin_dimension.setText(",".join(str(x) for x in data['dimension']))
        if 'resolution'in data:
            self.lin_resolution.setText(str(data['resolution']))
        if 'conversion' in data:
            self.lin_conversion.setText(str(data['conversion']))
        if 'timestamps' in data:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in data:
            self.chk_starting_time.setChecked(True)
        if 'rate' in data:
            self.chk_rate.setChecked(True)
        if 'comments' in data:
            self.lin_comments.setText(data['comments'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)



class GroupCorrectedImageStack(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.CorrectedImageStack fields filling form."""
        super().__init__()
        self.setTitle('CorrectedImageStack')
        self.parent = parent
        self.group_name = 'CorrectedImageStack'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('CorrectedImageStack')
        self.lin_name.setToolTip("The name of this CorrectedImageStack container")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCorrectedImageStack):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('CorrectedImageStack'+str(nInstances))

        self.lbl_corrected = QLabel('corrected:')
        self.chk_corrected = QCheckBox("Get from source file")
        self.chk_corrected.setChecked(True)
        self.chk_corrected.setToolTip("Image stack with frames shifted to the common "
            "coordinates.\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_original = QLabel('original:')
        self.combo_original = QComboBox()
        self.combo_original.setToolTip("Link to image series that is being registered.")

        self.lbl_xy_translation = QLabel('xy_translation:')
        self.chk_xy_translation = QCheckBox("Get from source file")
        self.chk_xy_translation.setChecked(True)
        self.chk_xy_translation.setToolTip("Stores the x,y delta necessary to align "
            "each frame to the common coordinates, for example, to align each frame "
            "to a reference image.\nCheck box if this data will be retrieved from "
            "source file.\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_corrected, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_corrected, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_original, 2, 0, 1, 2)
        self.grid.addWidget(self.combo_original, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_xy_translation, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_xy_translation, 3, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_original.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupTwoPhotonSeries):
                self.combo_original.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        if self.chk_corrected.isChecked():
            data['corrected'] = True
        data['original'] = str(self.combo_original.currentText())
        if self.chk_xy_translation.isChecked():
            data['xy_translation'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        if 'corrected' in data:
            self.chk_corrected.setChecked(True)
        self.combo_original.clear()
        self.combo_original.addItem(data['original'])
        if 'xy_translation' in data:
            self.chk_xy_translation.setChecked(True)



class GroupMotionCorrection(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.MotionCorrection fields filling form."""
        super().__init__()
        self.setTitle('MotionCorrection')
        self.parent = parent
        self.group_name = 'MotionCorrection'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('MotionCorrection')
        self.lin_name.setToolTip("The name of this MotionCorrection container")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupMotionCorrection):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('MotionCorrection'+str(nInstances))

        self.lbl_corrected_images_stacks = QLabel('corrected_images:')
        self.combo_corrected_images_stacks = QComboBox()
        self.combo_corrected_images_stacks.setToolTip("CorrectedImageStack to store in this interface.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_corrected_images_stacks, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_corrected_images_stacks, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_corrected_images_stacks.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCorrectedImageStack):
                self.combo_corrected_images_stacks.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['corrected_images_stacks'] = str(self.combo_corrected_images_stacks.currentText())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_corrected_images_stacks.clear()
        self.combo_corrected_images_stacks.addItem(data['corrected_images_stacks'])



class GroupPlaneSegmentation(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.PlaneSegmentation fields filling form."""
        super().__init__()
        self.setTitle('PlaneSegmentation')
        self.parent = parent
        self.group_name = 'PlaneSegmentation'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('PlaneSegmentation')
        self.lin_name.setToolTip("The name of this PlaneSegmentation.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupPlaneSegmentation):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('PlaneSegmentation'+str(nInstances))

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('description')
        self.lin_description.setToolTip(" Description of image plane, recording "
            "wavelength, depth, etc.")

        self.lbl_imaging_plane = QLabel('imaging_plane:')
        self.combo_imaging_plane = QComboBox()
        self.combo_imaging_plane.setToolTip("The ImagingPlane this ROI applies to.")

        self.lbl_reference_images = QLabel('reference_images:')
        self.chk_reference_images = QCheckBox("Get from source file")
        self.chk_reference_images.setChecked(False)
        self.chk_reference_images.setToolTip("One or more image stacks that the "
            "masks apply to (can be oneelement stack).\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_plane, 2, 0, 1, 2)
        self.grid.addWidget(self.combo_imaging_plane, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_reference_images, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_reference_images, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_imaging_plane.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupImagingPlane):
                self.combo_imaging_plane.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['description'] = self.lin_description.text()
        data['imaging_plane'] = self.combo_imaging_plane.currentText()
        if self.chk_reference_images.isChecked():
            data['reference_images'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        self.combo_imaging_plane.clear()
        self.combo_imaging_plane.addItem(data['imaging_plane'])
        if 'reference_images' in data:
            self.chk_reference_images.setChecked(True)



class GroupImageSegmentation(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.ImageSegmentation fields filling form."""
        super().__init__()
        self.setTitle('ImageSegmentation')
        self.parent = parent
        self.group_name = 'ImageSegmentation'

        # Name: it has a special treatment, since it need to be unique we test
        # if the parent contain other objects of the same type
        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('ImageSegmentation')
        self.lin_name.setToolTip("The name of this ImageSegmentation.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupImageSegmentation):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('ImageSegmentation'+str(nInstances))

        self.lbl_plane_segmentations = QLabel('plane_segmentations:')
        self.combo_plane_segmentations = QComboBox()
        self.combo_plane_segmentations.setToolTip("PlaneSegmentation to store in this interface.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_plane_segmentations, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_plane_segmentations, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_plane_segmentations.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupPlaneSegmentation):
                self.combo_plane_segmentations.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['plane_segmentations'] = str(self.combo_plane_segmentations.currentText())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_plane_segmentations.clear()
        self.combo_plane_segmentations.addItem(data['plane_segmentations'])



class GroupRoiResponseSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.RoiResponseSeries fields filling form."""
        super().__init__()
        self.setTitle('RoiResponseSeries')
        self.parent = parent
        self.group_name = 'RoiResponseSeries'

        # Name: it has a special treatment, since it need to be unique we test
        # if the parent contain other objects of the same type
        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('RoiResponseSeries')
        self.lin_name.setToolTip("The name of this RoiResponseSeries dataset.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupRoiResponseSeries):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('RoiResponseSeries'+str(nInstances))

        self.lbl_data = QLabel('data:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(True)
        self.chk_data.setToolTip("The data this TimeSeries dataset stores.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_unit = QLabel('unit:')
        self.lin_unit = QLineEdit('NA')
        self.lin_unit.setToolTip("The base unit of measurement (should be SI unit)")

        self.lbl_rois = QLabel('rois:')
        self.chk_rois = QCheckBox("Get from source file")
        self.chk_rois.setChecked(True)
        self.chk_rois.setToolTip("A table region corresponding to the ROIs that "
            "were used to generate this data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
        self.lin_resolution.setToolTip("The smallest meaningful difference (in "
            "specified unit) between values in data")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to convert to volts")

        self.lbl_timestamps = QLabel("timestamps:")
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip("Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_starting_time = QLabel("starting_time:")
        self.chk_starting_time = QCheckBox("Get from source file")
        self.chk_starting_time.setChecked(False)
        self.chk_starting_time.setToolTip("The timestamp of the first sample.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_rate = QLabel("rate:")
        self.chk_rate = QCheckBox("Get from source file")
        self.chk_rate.setChecked(False)
        self.chk_rate.setToolTip("Sampling rate in Hz.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_comments = QLabel("comments:")
        self.lin_comments = QLineEdit("")
        self.lin_comments.setPlaceholderText("comments")
        self.lin_comments.setToolTip("Human-readable comments about this TimeSeries dataset")

        self.lbl_description = QLabel("description:")
        self.lin_description = QLineEdit("")
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip("Description of this TimeSeries dataset")

        self.lbl_control = QLabel("control:")
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip("Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_control_description = QLabel("control_description:")
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip("Description of each control value.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_unit, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_unit, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_rois, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_rois, 3, 2, 1, 2)
        self.grid.addWidget(self.lbl_resolution, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 5, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 6, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 6, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 7, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_time, 7, 2, 1, 2)
        self.grid.addWidget(self.lbl_rate, 8, 0, 1, 2)
        self.grid.addWidget(self.chk_rate, 8, 2, 1, 2)
        self.grid.addWidget(self.lbl_comments, 9, 0, 1, 2)
        self.grid.addWidget(self.lin_comments, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 10, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 11, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 11, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 12, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 12, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        if self.chk_data.isChecked():
            data['data'] = True
        data['unit'] = self.lin_unit.text()
        if self.chk_rois.isChecked():
            data['rois'] = True
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except:
            pass
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except:
            pass
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        if self.chk_starting_time.isChecked():
            data['starting_time'] = True
        if self.chk_rate.isChecked():
            data['rate'] = True
        data['comments'] = self.lin_comments.text()
        data['description'] = self.lin_description.text()
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        if 'data' in data:
            self.chk_data.setChecked(True)
        if 'unit' in data:
            self.lin_unit.setText(data['unit'])
        if 'rois' in data:
            self.chk_rois.setChecked(True)
        if 'resolution' in data:
            self.lin_resolution.setText(str(data['resolution']))
        if 'conversion' in data:
            self.lin_conversion.setText(str(data['conversion']))
        if 'timestamps' in data:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in data:
            self.chk_starting_time.setChecked(True)
        if 'rate' in data:
            self.chk_rate.setChecked(True)
        if 'comments' in data:
            self.lin_comments.setText(data['comments'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)



class GroupDfOverF(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.DfOverF fields filling form."""
        super().__init__()
        self.setTitle('DfOverF')
        self.parent = parent
        self.group_name = 'DfOverF'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('DfOverF')
        self.lin_name.setToolTip("The name of this DfOverF.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupDfOverF):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('DfOverF'+str(nInstances))

        self.lbl_roi_response_series = QLabel('roi_response_series:')
        self.combo_roi_response_series = QComboBox()
        self.combo_roi_response_series.setToolTip("RoiResponseSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_roi_response_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_roi_response_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_roi_response_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupRoiResponseSeries):
                self.combo_roi_response_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['roi_response_series'] = str(self.combo_roi_response_series.currentText())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_roi_response_series.clear()
        self.combo_roi_response_series.addItem(data['roi_response_series'])



class GroupFluorescence(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.Fluorescence fields filling form."""
        super().__init__()
        self.setTitle('Fluorescence')
        self.parent = parent
        self.group_name = 'Fluorescence'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('Fluorescence')
        self.lin_name.setToolTip("The name of this Fluorescence.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupFluorescence):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('Fluorescence'+str(nInstances))

        self.lbl_roi_response_series = QLabel('roi_response_series:')
        self.combo_roi_response_series = QComboBox()
        self.combo_roi_response_series.setToolTip("RoiResponseSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_roi_response_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_roi_response_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_roi_response_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupRoiResponseSeries):
                self.combo_roi_response_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['roi_response_series'] = str(self.combo_roi_response_series.currentText())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_roi_response_series.clear()
        self.combo_roi_response_series.addItem(data['roi_response_series'])



class GroupGrayscaleVolume(QGroupBox):
    def __init__(self, parent):
        """Groupbox for GrayscaleVolume fields filling form."""
        super().__init__()
        self.setTitle('GrayscaleVolume')
        self.parent = parent
        self.group_name = 'GrayscaleVolume'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('GrayscaleVolume')
        self.lin_name.setToolTip("The unique name of this group.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupGrayscaleVolume):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('GrayscaleVolume'+str(nInstances))

        self.lbl_data = QLabel('data:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(True)
        self.chk_data.setToolTip("Dataset for this volumetric image.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_spatial_scale = QLabel('spatial_scale:')
        self.chk_spatial_scale = QCheckBox("Get from source file")
        self.chk_spatial_scale.setChecked(False)
        self.chk_spatial_scale.setToolTip("Spatial scale for this volumetric image.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_spatial_scale, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_spatial_scale, 2, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        if self.chk_data.isChecked():
            data['data'] = True
        if self.chk_spatial_scale.isChecked():
            data['spatial_scale'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        if 'data' in data:
            self.chk_data.setChecked(True)
        if 'spatial_scale' in data:
            self.chk_spatial_scale.setChecked(True)




class GroupOphys(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Ophys module fields filling form."""
        super().__init__()
        self.setTitle('Ophys')
        self.group_name = 'Ophys'
        self.groups_list = []

        self.combo1 = CustomComboBox()
        self.combo1.addItem('-- Add group --')
        self.combo1.addItem('Device')
        self.combo1.addItem('OpticalChannel')
        self.combo1.addItem('ImagingPlane')
        self.combo1.addItem('TwoPhotonSeries')
        self.combo1.addItem('CorrectedImageStack')
        self.combo1.addItem('MotionCorrection')
        self.combo1.addItem('PlaneSegmentation')
        self.combo1.addItem('ImageSegmentation')
        self.combo1.addItem('RoiResponseSeries')
        self.combo1.addItem('DfOverF')
        self.combo1.addItem('Fluorescence')
        self.combo1.addItem('GrayscaleVolume')
        self.combo1.setCurrentIndex(0)
        self.combo1.activated.connect(lambda: self.add_group('combo'))
        self.combo2 = CustomComboBox()
        self.combo2.addItem('-- Del group --')
        self.combo2.setCurrentIndex(0)
        self.combo2.activated.connect(lambda: self.del_group('combo'))

        self.vbox1 = QVBoxLayout()
        self.vbox1.addStretch()

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.combo1, 1, 0, 1, 2)
        self.grid.addWidget(self.combo2, 1, 2, 1, 2)
        self.grid.addLayout(self.vbox1, 2, 0, 1, 6)
        self.setLayout(self.grid)


    def add_group(self, group_type, write_data=None):
        """Adds group form."""
        if group_type=='combo':
            group_type = str(self.combo1.currentText())
        if group_type == 'Device':
            item = GroupDevice(self)
        elif group_type == 'OpticalChannel':
            item = GroupOpticalChannel(self)
        elif group_type == 'ImagingPlane':
            item = GroupImagingPlane(self)
        elif group_type == 'TwoPhotonSeries':
            item = GroupTwoPhotonSeries(self)
        elif group_type == 'CorrectedImageStack':
            item = GroupCorrectedImageStack(self)
        elif group_type == 'MotionCorrection':
            item = GroupMotionCorrection(self)
        elif group_type == 'PlaneSegmentation':
            item = GroupPlaneSegmentation(self)
        elif group_type == 'ImageSegmentation':
            item = GroupImageSegmentation(self)
        elif group_type == 'RoiResponseSeries':
            item = GroupRoiResponseSeries(self)
        elif group_type == 'DfOverF':
            item = GroupDfOverF(self)
        elif group_type == 'Fluorescence':
            item = GroupFluorescence(self)
        elif group_type == 'GrayscaleVolume':
            item = GroupGrayscaleVolume(self)
        if group_type != '-- Add group --':
            if write_data is not None:
                item.write_fields(data=write_data)
            item.lin_name.textChanged.connect(self.refresh_del_combo)
            self.groups_list.append(item)
            nWidgetsVbox = self.vbox1.count()
            self.vbox1.insertWidget(nWidgetsVbox-1, item) #insert before the stretch
            self.combo1.setCurrentIndex(0)
            self.combo2.addItem(item.lin_name.text())
            self.refresh_children()

    def del_group(self, group_name):
        """Deletes group form by name."""
        if group_name=='combo':
            group_name = str(self.combo2.currentText())
        if group_name != '-- Del group --':
            nWidgetsVbox = self.vbox1.count()
            for i in range(nWidgetsVbox):
                if self.vbox1.itemAt(i) is not None:
                    if (hasattr(self.vbox1.itemAt(i).widget(), 'lin_name')) and \
                        (self.vbox1.itemAt(i).widget().lin_name.text()==group_name):
                        self.groups_list.remove(self.vbox1.itemAt(i).widget())   #deletes list item
                        self.vbox1.itemAt(i).widget().setParent(None)            #deletes widget
                        self.combo2.removeItem(self.combo2.findText(group_name))
                        self.combo2.setCurrentIndex(0)
                        self.refresh_children()

    def refresh_children(self):
        """Refreshes references with existing objects in child groups."""
        for child in self.groups_list:
            child.refresh_objects_references()

    def refresh_del_combo(self):
        """Refreshes del combobox with existing objects names in child groups."""
        self.combo2.clear()
        self.combo2.addItem('-- Del group --')
        for child in self.groups_list:
            self.combo2.addItem(child.lin_name.text())
        self.refresh_children()

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        for grp in self.groups_list:
            data[grp.group_name] = grp.read_fields()
        return data




class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
