from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                             QGroupBox, QComboBox, QCheckBox, QMessageBox)
from PySide2.QtGui import QDoubleValidator
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox
from itertools import groupby


class GroupOpticalChannel(QGroupBox):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.ophys.OpticalChannel fields filling form."""
        super().__init__()
        self.setTitle('OpticalChannel')
        self.parent = parent
        self.group_type = 'OpticalChannel'

        validator_float = QDoubleValidator()

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'name' in metadata:
            self.form_name = QLineEdit(metadata['name'])
        else:
            self.form_name = QLineEdit('OpticalChannel')
        self.form_name.setToolTip("the name of this optical channel")

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'description' in metadata:
            self.form_description = QLineEdit(metadata['description'])
        else:
            self.form_description = QLineEdit('description')
        self.form_description.setToolTip("Any notes or comments about the channel")

        self.lbl_emission_lambda = QLabel('emission_lambda<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'emission_lambda' in metadata:
            self.form_emission_lambda = QLineEdit(str(metadata['emission_lambda']))
        else:
            self.form_emission_lambda = QLineEdit('0.0')
        self.form_emission_lambda.setToolTip("Emission lambda for channel")
        self.form_emission_lambda.setValidator(validator_float)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.form_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_emission_lambda, 2, 0, 1, 2)
        self.grid.addWidget(self.form_emission_lambda, 2, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['description'] = self.form_description.text()
        try:
            data['emission_lambda'] = float(self.form_emission_lambda.text())
        except ValueError as error:
            print(error)
            data['emission_lambda'] = 0.0
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.form_description.setText(metadata['description'])
        self.form_emission_lambda.setText(str(metadata['emission_lambda']))


#class GroupImagingPlane(QGroupBox):
class GroupImagingPlane(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.ImagingPlane fields filling form."""
        super().__init__(title='ImagingPlane', parent=parent)
        #self.setTitle('ImagingPlane')
        self.parent = parent
        self.group_type = 'ImagingPlane'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('ImagingPlane')
        self.form_name.setToolTip("The name of this ImagingPlane")

        self.lbl_optical_channel = QLabel('optical_channel<span style="color:'+required_asterisk_color+';">*</span>:')
        self.optical_channel_layout = QVBoxLayout()
        self.optical_channel = QGroupBox()
        self.optical_channel.setLayout(self.optical_channel_layout)
        self.optical_channel.setToolTip(
            "One of possibly many groups storing channels pecific data")

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_description = QLineEdit('description')
        self.form_description.setToolTip("Description of this ImagingPlane")

        self.lbl_device = QLabel('device<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_device = CustomComboBox()
        self.combo_device.setToolTip("The device that was used to record")

        self.lbl_excitation_lambda = QLabel('excitation_lambda<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_excitation_lambda = QLineEdit('0.0')
        self.form_excitation_lambda.setToolTip("Excitation wavelength in nm")

        self.lbl_imaging_rate = QLabel('imaging_rate<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_imaging_rate = QLineEdit('0.0')
        self.form_imaging_rate.setToolTip("Rate images are acquired, in Hz")

        self.lbl_indicator = QLabel('indicator<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_indicator = QLineEdit('indicator')
        self.form_indicator.setToolTip("Calcium indicator")

        self.lbl_location = QLabel('location<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_location = QLineEdit('location')
        self.form_location.setToolTip("Location of image plane")

        self.lbl_manifold = QLabel('manifold:')
        self.chk_manifold = QCheckBox("Get from source file")
        self.chk_manifold.setChecked(False)
        self.chk_manifold.setToolTip(
            "Physical position of each pixel. size=(height, width, xyz).\n "
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_conversion = QLabel('conversion:')
        self.form_conversion = QLineEdit('')
        self.form_conversion.setPlaceholderText("1")
        self.form_conversion.setToolTip(
            "Multiplier to get from stored values to specified unit (e.g., 1e-3 for millimeters)")

        self.lbl_unit = QLabel('unit:')
        self.form_unit = QLineEdit('')
        self.form_unit.setPlaceholderText("meters")
        self.form_unit.setToolTip("Base unit that coordinates are stored in (e.g., Meters)")

        self.lbl_reference_frame = QLabel('reference_frame:')
        self.form_reference_frame = QLineEdit('')
        self.form_reference_frame.setPlaceholderText("reference_frame")
        self.form_reference_frame.setToolTip(
            "Describes position and reference frame of manifold based on position "
            "of first element in manifold.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_optical_channel, 1, 0, 1, 2)
        self.grid.addWidget(self.optical_channel, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.form_description, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_device, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_device, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_excitation_lambda, 4, 0, 1, 2)
        self.grid.addWidget(self.form_excitation_lambda, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_rate, 5, 0, 1, 2)
        self.grid.addWidget(self.form_imaging_rate, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_indicator, 6, 0, 1, 2)
        self.grid.addWidget(self.form_indicator, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_location, 7, 0, 1, 2)
        self.grid.addWidget(self.form_location, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_manifold, 8, 0, 1, 2)
        self.grid.addWidget(self.chk_manifold, 8, 2, 1, 2)
        self.grid.addWidget(self.lbl_conversion, 9, 0, 1, 2)
        self.grid.addWidget(self.form_conversion, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_unit, 10, 0, 1, 2)
        self.grid.addWidget(self.form_unit, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_reference_frame, 11, 0, 1, 2)
        self.grid.addWidget(self.form_reference_frame, 11, 2, 1, 4)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_device.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupDevice):
                self.combo_device.addItem(grp.form_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['optical_channel'] = []
        nItems = self.optical_channel_layout.count()
        for i in range(nItems):
            item = self.optical_channel_layout.itemAt(i).widget()
            data['optical_channel'].append(item.read_fields())
        data['description'] = self.form_description.text()
        data['device'] = str(self.combo_device.currentText())
        try:
            data['excitation_lambda'] = float(self.form_excitation_lambda.text())
        except ValueError as error:
            print(error)
            data['excitation_lambda'] = 0.0
        try:
            data['imaging_rate'] = float(self.form_imaging_rate.text())
        except ValueError as error:
            print(error)
            data['imaging_rate'] = 0.0
        data['indicator'] = self.form_indicator.text()
        data['location'] = self.form_location.text()
        if self.chk_manifold.isChecked():
            data['manifold'] = True
        try:
            data['conversion'] = float(self.form_conversion.text())
        except ValueError as error:
            print(error)
            data['conversion'] = 0.0
        data['unit'] = self.form_unit.text()
        data['reference_frame'] = self.form_reference_frame.text()
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        nItems = self.optical_channel_layout.count()
        for ind, sps in enumerate(metadata['optical_channel']):
            if ind >= nItems:
                item = GroupOpticalChannel(self, metadata=metadata['optical_channel'][ind])
                self.optical_channel_layout.addWidget(item)
        if 'description' in data:
            self.form_description.setText(metadata['description'])
        self.combo_device.clear()
        self.combo_device.addItem(metadata['device'])
        self.form_excitation_lambda.setText(str(metadata['excitation_lambda']))
        self.form_imaging_rate.setText(str(metadata['imaging_rate']))
        self.form_indicator.setText(str(metadata['indicator']))
        self.form_location.setText(str(metadata['location']))
        if 'conversion' in metadata:
            self.form_conversion.setText(str(metadata['conversion']))
        if 'unit' in data:
            self.form_unit.setText(metadata['unit'])
        if 'reference_frame' in data:
            self.form_reference_frame.setText(metadata['reference_frame'])
        self.setContentLayout(self.grid)


#class GroupTwoPhotonSeries(QGroupBox):
class GroupTwoPhotonSeries(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.TwoPhotonSeries fields filling form."""
        super().__init__(title='TwoPhotonSeries', parent=parent)
        #self.setTitle('TwoPhotonSeries')
        self.parent = parent
        self.group_type = 'TwoPhotonSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('TwoPhotonSeries')
        self.form_name.setToolTip("The name of this TimeSeries dataset")

        self.lbl_imaging_plane = QLabel('imaging_plane<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_imaging_plane = CustomComboBox()
        self.combo_imaging_plane.setToolTip("Imaging plane class/pointer")

        self.lbl_unit = QLabel('unit:')
        self.form_unit = QLineEdit('')
        self.form_unit.setPlaceholderText("unit")
        self.form_unit.setToolTip("The base unit of measurement (should be SI unit)")

        self.lbl_format = QLabel("format:")
        self.form_format = QLineEdit("")
        self.form_format.setPlaceholderText("format")
        self.form_format.setToolTip(
            "Format of image. Three types: 1) Image format: tiff, png, jpg, etc. 2) external 3) raw")

        self.lbl_field_of_view = QLabel("field_of_view:")
        self.chk_field_of_view = QCheckBox("Get from source file")
        self.chk_field_of_view.setChecked(False)
        self.chk_field_of_view.setToolTip(
            "Width, height and depth of image, or imaged area (meters)."
            "\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_pmt_gain = QLabel("pmt_gain:")
        self.form_pmt_gain = QLineEdit("")
        self.form_pmt_gain.setPlaceholderText("1.0")
        self.form_pmt_gain.setToolTip("Photomultiplier gain")

        self.lbl_scan_line_rate = QLabel("scan_line_rate:")
        self.form_scan_line_rate = QLineEdit("")
        self.form_scan_line_rate.setPlaceholderText("0.0")
        self.form_scan_line_rate.setToolTip("Lines imaged per second")

        self.lbl_external_file = QLabel("external_file:")
        self.form_external_file = QLineEdit("")
        self.form_external_file.setPlaceholderText("path/to/external_file")
        self.form_external_file.setToolTip(
            "Path or URL to one or more external file(s). Field only present if format=external."
            "\nEither external_file or data must be specified, but not both.")

        self.lbl_starting_frame = QLabel("starting_frame:")
        self.chk_starting_frame = QCheckBox("Get from source file")
        self.chk_starting_frame.setChecked(False)
        self.chk_starting_frame.setToolTip(
            "Each entry is the frame number in the corresponding external_file variable."
            "\nThis serves as an index to what frames each file contains."
            "\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_bits_per_pixel = QLabel("bits_per_pixel:")
        self.form_bits_per_pixel = QLineEdit("")
        self.form_bits_per_pixel.setPlaceholderText("1")
        self.form_bits_per_pixel.setToolTip("Number of bit per image pixel")

        self.lbl_dimension = QLabel("dimension:")
        self.form_dimension = QLineEdit("")
        self.form_dimension.setPlaceholderText("1,1,1")
        self.form_dimension.setToolTip("Number of pixels on x, y, (and z) axes")

        self.lbl_resolution = QLabel("resolution:")
        self.form_resolution = QLineEdit("")
        self.form_resolution.setToolTip(
            "The smallest meaningful difference (in specified unit) between values in data")

        self.lbl_conversion = QLabel("conversion:")
        self.form_conversion = QLineEdit("")
        self.form_conversion.setPlaceholderText("1.0")
        self.form_conversion.setToolTip("Scalar to multiply each element by to convert to volts")

        self.lbl_timestamps = QLabel("timestamps:")
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_starting_time = QLabel("starting_time:")
        self.chk_starting_time = QCheckBox("Get from source file")
        self.chk_starting_time.setChecked(False)
        self.chk_starting_time.setToolTip(
            "The timestamp of the first sample.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_rate = QLabel("rate:")
        self.chk_rate = QCheckBox("Get from source file")
        self.chk_rate.setChecked(False)
        self.chk_rate.setToolTip(
            "Sampling rate in Hz.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_comments = QLabel("comments:")
        self.form_comments = QLineEdit("")
        self.form_comments.setPlaceholderText("comments")
        self.form_comments.setToolTip("Human-readable comments about this TimeSeries dataset")

        self.lbl_description = QLabel("description:")
        self.form_description = QLineEdit("")
        self.form_description.setPlaceholderText("description")
        self.form_description.setToolTip("Description of this TimeSeries dataset")

        self.lbl_control = QLabel("control:")
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip(
            "Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_control_description = QLabel("control_description:")
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip(
            "Description of each control value.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_plane, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_imaging_plane, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_unit, 3, 0, 1, 2)
        self.grid.addWidget(self.form_unit, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_format, 4, 0, 1, 2)
        self.grid.addWidget(self.form_format, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_field_of_view, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_field_of_view, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_pmt_gain, 6, 0, 1, 2)
        self.grid.addWidget(self.form_pmt_gain, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_scan_line_rate, 7, 0, 1, 2)
        self.grid.addWidget(self.form_scan_line_rate, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_external_file, 8, 0, 1, 2)
        self.grid.addWidget(self.form_external_file, 8, 2, 1, 4)
        self.grid.addWidget(self.lbl_starting_frame, 9, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_frame, 9, 2, 1, 2)
        self.grid.addWidget(self.lbl_bits_per_pixel, 10, 0, 1, 2)
        self.grid.addWidget(self.form_bits_per_pixel, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_dimension, 11, 0, 1, 2)
        self.grid.addWidget(self.form_dimension, 11, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 12, 0, 1, 2)
        self.grid.addWidget(self.form_resolution, 12, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 13, 0, 1, 2)
        self.grid.addWidget(self.form_conversion, 13, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 14, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 14, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 15, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_time, 15, 2, 1, 2)
        self.grid.addWidget(self.lbl_rate, 16, 0, 1, 2)
        self.grid.addWidget(self.chk_rate, 16, 2, 1, 2)
        self.grid.addWidget(self.lbl_comments, 17, 0, 1, 2)
        self.grid.addWidget(self.form_comments, 17, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 18, 0, 1, 2)
        self.grid.addWidget(self.form_description, 18, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 19, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 19, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 20, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 20, 2, 1, 2)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_imaging_plane.clear()
        for grp in self.parent.groups_list:
            # Adds all existing ImagingPlanes to combobox
            if isinstance(grp, GroupImagingPlane):
                self.combo_imaging_plane.addItem(grp.form_name.text())
        # If metadata is referring to this specific object, update combobox item
        if metadata['name'] == self.form_name.text():
            self.combo_imaging_plane.setCurrentText(metadata['imaging_plane'])

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['imaging_plane'] = self.combo_imaging_plane.currentText()
        data['unit'] = self.form_unit.text()
        data['format'] = self.form_format.text()
        if self.chk_field_of_view.isChecked():
            data['field_of_view'] = True
        try:
            data['pmt_gain'] = float(self.form_pmt_gain.text())
        except ValueError as error:
            print(error)
        try:
            data['scan_line_rate'] = float(self.form_scan_line_rate.text())
        except ValueError as error:
            print(error)
        if self.form_format.text() == 'external':
            data['external_file'] = self.form_external_file.text()
            if self.chk_starting_frame.isChecked():
                data['starting_frame'] = True
        try:
            data['bits_per_pixel'] = int(self.form_bits_per_pixel.text())
        except ValueError as error:
            print(error)
        try:
            data['dimension'] = [int(it) for it in self.form_dimension.text().split(',')]
        except ValueError as error:
            print(error)
        try:
            data['resolution'] = float(self.form_resolution.text())
        except ValueError as error:
            print(error)
        try:
            data['conversion'] = float(self.form_conversion.text())
        except ValueError as error:
            print(error)
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        if self.chk_starting_time.isChecked():
            data['starting_time'] = True
        if self.chk_rate.isChecked():
            data['rate'] = True
        data['comments'] = self.form_comments.text()
        data['description'] = self.form_description.text()
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.combo_imaging_plane.clear()
        self.combo_imaging_plane.addItem(metadata['imaging_plane'])
        if 'unit' in metadata:
            self.form_unit.setText(metadata['unit'])
        if 'format' in metadata:
            self.form_format.setText(metadata['format'])
        if 'pmt_gain' in metadata:
            self.form_pmt_gain.setText(str(metadata['pmt_gain']))
        if 'scan_line_rate' in metadata:
            self.form_scan_line_rate.setText(str(metadata['scan_line_rate']))
        if 'external_file' in metadata:
            self.form_format.setText('external')
            self.form_external_file.setText(metadata['external_file'])
            self.chk_starting_frame.setChecked(False)
        else:
            self.form_format.setText('')
            self.form_external_file.setText('')
            self.chk_starting_frame.setChecked(True)
        if 'bits_per_pixel' in metadata:
            self.form_bits_per_pixel.setText(str(metadata['bits_per_pixel']))
        if 'dimension' in metadata:
            self.form_dimension.setText(",".join(str(x) for x in metadata['dimension']))
        if 'resolution'in metadata:
            self.form_resolution.setText(str(metadata['resolution']))
        if 'conversion' in metadata:
            self.form_conversion.setText(str(metadata['conversion']))
        if 'timestamps' in metadata:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in metadata:
            self.chk_starting_time.setChecked(True)
        if 'rate' in metadata:
            self.chk_rate.setChecked(True)
        if 'comments' in metadata:
            self.form_comments.setText(metadata['comments'])
        if 'description' in metadata:
            self.form_description.setText(metadata['description'])
        self.setContentLayout(self.grid)


class GroupCorrectedImageStack(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.CorrectedImageStack fields filling form."""
        super().__init__()
        self.setTitle('CorrectedImageStack')
        self.parent = parent
        self.group_type = 'CorrectedImageStack'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('CorrectedImageStack')
        self.form_name.setToolTip("The name of this CorrectedImageStack container")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCorrectedImageStack):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('CorrectedImageStack'+str(nInstances))

        self.lbl_corrected = QLabel('corrected<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_corrected = QCheckBox("Get from source file")
        self.chk_corrected.setChecked(True)
        self.chk_corrected.setToolTip(
            "Image stack with frames shifted to the common coordinates."
            "\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_original = QLabel('original<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_original = CustomComboBox()
        self.combo_original.setToolTip("Link to image series that is being registered.")

        self.lbl_xy_translation = QLabel('xy_translation<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_xy_translation = QCheckBox("Get from source file")
        self.chk_xy_translation.setChecked(True)
        self.chk_xy_translation.setToolTip(
            "Stores the x,y delta necessary to align each frame to the common coordinates,\n"
            "for example, to align each frame to a reference image."
            "\nCheck box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_corrected, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_corrected, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_original, 2, 0, 1, 2)
        self.grid.addWidget(self.combo_original, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_xy_translation, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_xy_translation, 3, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_original.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupTwoPhotonSeries):
                self.combo_original.addItem(grp.form_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        if self.chk_corrected.isChecked():
            data['corrected'] = True
        data['original'] = str(self.combo_original.currentText())
        if self.chk_xy_translation.isChecked():
            data['xy_translation'] = True
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.combo_original.clear()
        self.combo_original.addItem(metadata['original'])


class GroupMotionCorrection(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.MotionCorrection fields filling form."""
        super().__init__()
        self.setTitle('MotionCorrection')
        self.parent = parent
        self.group_type = 'MotionCorrection'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('MotionCorrection')
        self.form_name.setToolTip("The name of this MotionCorrection container")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupMotionCorrection):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('MotionCorrection'+str(nInstances))

        self.lbl_corrected_images_stacks = QLabel('corrected_images:')
        self.combo_corrected_images_stacks = CustomComboBox()
        self.combo_corrected_images_stacks.setToolTip("CorrectedImageStack to store in this interface.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_corrected_images_stacks, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_corrected_images_stacks, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_corrected_images_stacks.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCorrectedImageStack):
                self.combo_corrected_images_stacks.addItem(grp.form_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['corrected_images_stacks'] = str(self.combo_corrected_images_stacks.currentText())
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.combo_corrected_images_stacks.clear()
        self.combo_corrected_images_stacks.addItem(metadata['corrected_images_stacks'])


class GroupPlaneSegmentation(QGroupBox):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.ophys.PlaneSegmentation fields filling form."""
        super().__init__()
        self.setTitle('PlaneSegmentation')
        self.parent = parent
        self.group_type = 'PlaneSegmentation'
        if metadata is None:
            metadata = dict()

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'name' in metadata:
            self.form_name = QLineEdit(metadata['name'])
        else:
            self.form_name = QLineEdit('PlaneSegmentation')
        self.form_name.setToolTip("The name of this PlaneSegmentation.")

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'description' in metadata:
            self.form_description = QLineEdit(metadata['description'])
        else:
            self.form_description = QLineEdit('ADDME')
        self.form_description.setToolTip(
            "Description of image plane, recording wavelength, depth, etc.")

        self.lbl_imaging_plane = QLabel('imaging_plane<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_imaging_plane = CustomComboBox()
        self.combo_imaging_plane.setToolTip("The ImagingPlane this ROI applies to.")

        self.lbl_reference_images = QLabel('reference_images:')
        self.chk_reference_images = QCheckBox("Get from source file")
        if 'reference_images' in metadata:
            self.chk_reference_images.setChecked(metadata['reference_images'])
        else:
            self.chk_reference_images.setChecked(False)
        self.chk_reference_images.setToolTip(
            "One or more image stacks that the masks apply to (can be oneelement stack).\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.form_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_imaging_plane, 2, 0, 1, 2)
        self.grid.addWidget(self.combo_imaging_plane, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_reference_images, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_reference_images, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_imaging_plane.clear()
        for grp in self.parent.parent.groups_list:
            # Adds all existing ImagingPlanes to combobox
            if isinstance(grp, GroupImagingPlane):
                self.combo_imaging_plane.addItem(grp.form_name.text())
        # If metadata is referring to this specific object, update combobox item
        if metadata['name'] == self.form_name.text():
            self.combo_imaging_plane.setCurrentText(metadata['imaging_plane'])

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['description'] = self.form_description.text()
        data['imaging_plane'] = self.combo_imaging_plane.currentText()
        if self.chk_reference_images.isChecked():
            data['reference_images'] = True
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        if 'description' in metadata:
            self.form_description.setText(metadata['description'])
        self.combo_imaging_plane.clear()
        self.combo_imaging_plane.addItem(metadata['imaging_plane'])


#class GroupImageSegmentation(QGroupBox):
class GroupImageSegmentation(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.ImageSegmentation fields filling form."""
        super().__init__(title='ImageSegmentation', parent=parent)
        #self.setTitle('ImageSegmentation')
        self.parent = parent
        self.group_type = 'ImageSegmentation'
        self.groups_list = []

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('ImageSegmentation')
        self.form_name.setToolTip("The name of this ImageSegmentation.")

        self.lbl_plane_segmentations = QLabel('plane_segmentations:')
        self.plane_segmentations_layout = QVBoxLayout()
        self.plane_segmentations = QGroupBox()
        self.plane_segmentations.setLayout(self.plane_segmentations_layout)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_plane_segmentations, 1, 0, 1, 2)
        self.grid.addWidget(self.plane_segmentations, 1, 2, 1, 4)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        if metadata is None:
            metadata = {}
        for child in self.groups_list:
            # Get metadata corresponding to this specific child
            if 'plane_segmentations' in metadata:
                submeta = [sub for sub in metadata['plane_segmentations']
                           if sub['name'] == child.form_name.text()][0]
            else:
                submeta = metadata
            child.refresh_objects_references(metadata=submeta)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['plane_segmentations'] = []
        nItems = self.plane_segmentations_layout.count()
        for i in range(nItems):
            item = self.plane_segmentations_layout.itemAt(i).widget()
            data['plane_segmentations'].append(item.read_fields())
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        nItems = self.plane_segmentations_layout.count()
        for ind, sps in enumerate(metadata['plane_segmentations']):
            if ind >= nItems:
                item = GroupPlaneSegmentation(self, metadata=sps)
                self.groups_list.append(item)
                self.plane_segmentations_layout.addWidget(item)
        self.setContentLayout(self.grid)


class GroupRoiResponseSeries(QGroupBox):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.ophys.RoiResponseSeries fields filling form."""
        super().__init__()
        self.setTitle('RoiResponseSeries')
        self.parent = parent
        self.group_type = 'RoiResponseSeries'
        if metadata is None:
            metadata = dict()

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'name' in metadata:
            self.form_name = QLineEdit(metadata['name'])
        else:
            self.form_name = QLineEdit('RoiResponseSeries')
        self.form_name.setToolTip("The name of this RoiResponseSeries dataset.")

        self.lbl_unit = QLabel('unit<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'unit' in metadata:
            self.form_unit = QLineEdit(metadata['unit'])
        else:
            self.form_unit = QLineEdit('NA')
        self.form_unit.setToolTip("The base unit of measurement (should be SI unit)")

        self.lbl_rois = QLabel('rois<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_rois = QCheckBox("Get from source file")
        if 'rois' in metadata:
            self.chk_rois.setChecked(metadata['rois'])
        else:
            self.chk_rois.setChecked(True)
        self.chk_rois.setToolTip(
            "A table region corresponding to the ROIs that were used to generate this data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_resolution = QLabel('resolution:')
        if 'resolution' in metadata:
            self.form_resolution = QLineEdit(metadata['resolution'])
        else:
            self.form_resolution = QLineEdit('')
        self.form_resolution.setPlaceholderText("1.0")
        self.form_resolution.setToolTip(
            "The smallest meaningful difference (in specified unit) between values in data")

        self.lbl_conversion = QLabel('conversion:')
        if 'conversion' in metadata:
            self.form_conversion = QLineEdit(metadata['conversion'])
        else:
            self.form_conversion = QLineEdit('')
        self.form_conversion.setPlaceholderText("1.0")
        self.form_conversion.setToolTip("Scalar to multiply each element by to convert to volts")

        self.lbl_timestamps = QLabel("timestamps:")
        self.chk_timestamps = QCheckBox("Get from source file")
        if 'timestamps' in metadata:
            self.chk_timestamps.setChecked(metadata['timestamps'])
        else:
            self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_starting_time = QLabel("starting_time:")
        self.chk_starting_time = QCheckBox("Get from source file")
        if 'starting_time' in metadata:
            self.chk_starting_time.setChecked(metadata['starting_time'])
        else:
            self.chk_starting_time.setChecked(False)
        self.chk_starting_time.setToolTip(
            "The timestamp of the first sample.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_rate = QLabel("rate:")
        self.chk_rate = QCheckBox("Get from source file")
        if 'rate' in metadata:
            self.chk_rate.setChecked(metadata['rate'])
        else:
            self.chk_rate.setChecked(False)
        self.chk_rate.setToolTip(
            "Sampling rate in Hz.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_comments = QLabel("comments:")
        if 'comments' in metadata:
            self.form_comments = QLineEdit(metadata['comments'])
        else:
            self.form_comments = QLineEdit("")
        self.form_comments.setPlaceholderText("comments")
        self.form_comments.setToolTip("Human-readable comments about this TimeSeries dataset")

        self.lbl_description = QLabel("description:")
        if 'description' in metadata:
            self.form_description = QLineEdit(metadata['description'])
        else:
            self.form_description = QLineEdit("")
        self.form_description.setPlaceholderText("description")
        self.form_description.setToolTip("Description of this TimeSeries dataset")

        self.lbl_control = QLabel("control:")
        self.chk_control = QCheckBox("Get from source file")
        if 'control' in metadata:
            self.chk_control.setChecked(metadata['control'])
        else:
            self.chk_control.setChecked(False)
        self.chk_control.setToolTip(
            "Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.lbl_control_description = QLabel("control_description:")
        self.chk_control_description = QCheckBox("Get from source file")
        if 'control_description' in metadata:
            self.chk_control_description.setChecked(metadata['control_description'])
        else:
            self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip(
            "Description of each control value.\n"
            "Check box if this data will be retrieved from source file."
            "\nUncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_unit, 2, 0, 1, 2)
        self.grid.addWidget(self.form_unit, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_rois, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_rois, 3, 2, 1, 2)
        self.grid.addWidget(self.lbl_resolution, 4, 0, 1, 2)
        self.grid.addWidget(self.form_resolution, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 5, 0, 1, 2)
        self.grid.addWidget(self.form_conversion, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 6, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 6, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 7, 0, 1, 2)
        self.grid.addWidget(self.chk_starting_time, 7, 2, 1, 2)
        self.grid.addWidget(self.lbl_rate, 8, 0, 1, 2)
        self.grid.addWidget(self.chk_rate, 8, 2, 1, 2)
        self.grid.addWidget(self.lbl_comments, 9, 0, 1, 2)
        self.grid.addWidget(self.form_comments, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 10, 0, 1, 2)
        self.grid.addWidget(self.form_description, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 11, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 11, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 12, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 12, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['unit'] = self.form_unit.text()
        if self.chk_rois.isChecked():
            data['rois'] = True
        try:
            data['resolution'] = float(self.form_resolution.text())
        except ValueError as error:
            print(error)
        try:
            data['conversion'] = float(self.form_conversion.text())
        except ValueError as error:
            print(error)
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        if self.chk_starting_time.isChecked():
            data['starting_time'] = True
        if self.chk_rate.isChecked():
            data['rate'] = True
        data['comments'] = self.form_comments.text()
        data['description'] = self.form_description.text()
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        if 'unit' in metadata:
            self.form_unit.setText(metadata['unit'])
        if 'resolution' in metadata:
            self.form_resolution.setText(str(metadata['resolution']))
        if 'conversion' in metadata:
            self.form_conversion.setText(str(metadata['conversion']))
        if 'timestamps' in metadata:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in metadata:
            self.chk_starting_time.setChecked(True)
        if 'rate' in metadata:
            self.chk_rate.setChecked(True)
        if 'comments' in metadata:
            self.form_comments.setText(metadata['comments'])
        if 'description' in metadata:
            self.form_description.setText(metadata['description'])


#class GroupDfOverF(QGroupBox):
class GroupDfOverF(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.DfOverF fields filling form."""
        super().__init__(title='DfOverF', parent=parent)
        #self.setTitle('DfOverF')
        self.parent = parent
        self.group_type = 'DfOverF'
        self.groups_list = []

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('DfOverF')
        self.form_name.setToolTip("The name of this DfOverF.")

        self.lbl_roi_response_series = QLabel('roi_response_series:')
        self.roi_response_series_layout = QVBoxLayout()
        self.roi_response_series = QGroupBox()
        self.roi_response_series.setLayout(self.roi_response_series_layout)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_roi_response_series, 1, 0, 1, 2)
        self.grid.addWidget(self.roi_response_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['roi_response_series'] = []
        nItems = self.roi_response_series_layout.count()
        for i in range(nItems):
            item = self.roi_response_series_layout.itemAt(i).widget()
            data['roi_response_series'].append(item.read_fields())
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        nItems = self.roi_response_series_layout.count()
        for ind, rrs in enumerate(metadata['roi_response_series']):
            if ind >= nItems:
                item = GroupRoiResponseSeries(self, metadata=rrs)
                self.groups_list.append(item)
                self.roi_response_series_layout.addWidget(item)
        self.setContentLayout(self.grid)


class GroupFluorescence(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ophys.Fluorescence fields filling form."""
        super().__init__()
        self.setTitle('Fluorescence')
        self.parent = parent
        self.group_type = 'Fluorescence'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('Fluorescence')
        self.form_name.setToolTip("The name of this Fluorescence.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupFluorescence):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('Fluorescence'+str(nInstances))

        self.lbl_roi_response_series = QLabel('roi_response_series:')
        self.combo_roi_response_series = CustomComboBox()
        self.combo_roi_response_series.setToolTip("RoiResponseSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_roi_response_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_roi_response_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_roi_response_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupRoiResponseSeries):
                self.combo_roi_response_series.addItem(grp.form_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['roi_response_series'] = str(self.combo_roi_response_series.currentText())
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.combo_roi_response_series.clear()
        self.combo_roi_response_series.addItem(metadata['roi_response_series'])


#class GroupGrayscaleVolume(QGroupBox):
class GroupGrayscaleVolume(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for GrayscaleVolume fields filling form."""
        super().__init__(title='GrayscaleVolume', parent=parent)
        #self.setTitle('GrayscaleVolume')
        self.parent = parent
        self.group_type = 'GrayscaleVolume'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('GrayscaleVolume')
        self.form_name.setToolTip("The unique name of this group.")

        self.lbl_spatial_scale = QLabel('spatial_scale:')
        self.chk_spatial_scale = QCheckBox("Get from source file")
        self.chk_spatial_scale.setChecked(False)
        self.chk_spatial_scale.setToolTip(
            "Spatial scale for this volumetric image.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_spatial_scale, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_spatial_scale, 2, 2, 1, 2)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        if self.chk_spatial_scale.isChecked():
            data['spatial_scale'] = True
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(metadata['name'])
        self.setContentLayout(self.grid)


class GroupOphys(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Ophys module fields filling form."""
        super().__init__()
        self.setTitle('Ophys')
        self.group_type = 'Ophys'
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
        self.combo1.addItem('FRET')
        self.combo1.addItem('FRETSeries')
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
        if parent.show_add_del:
            self.grid.addWidget(self.combo1, 1, 0, 1, 2)
            self.grid.addWidget(self.combo2, 1, 2, 1, 2)
        self.grid.addLayout(self.vbox1, 2, 0, 1, 6)
        self.setLayout(self.grid)

    def add_group(self, group, metadata=None):
        """Adds group form."""
        if metadata is not None:
            group.write_fields(metadata=metadata)
        group.form_name.textChanged.connect(self.refresh_del_combo)
        self.groups_list.append(group)
        nWidgetsVbox = self.vbox1.count()
        self.vbox1.insertWidget(nWidgetsVbox-1, group)  # insert before the stretch
        self.combo1.setCurrentIndex(0)
        #self.combo2.addItem(group.form_name.text())
        self.refresh_children(metadata=metadata)

    def del_group(self, group_name):
        """Deletes group form by name."""
        if group_name == 'combo':
            group_name = str(self.combo2.currentText())
        if group_name != '-- Del group --':
            # Tests if any other group references this one
            if self.is_referenced(grp_unique_name=group_name):
                QMessageBox.warning(self, "Cannot delete subgroup",
                                    group_name+" is being referenced by another subgroup(s).\n"
                                    "You should remove any references of "+group_name+" before "
                                    "deleting it!")
                self.combo2.setCurrentIndex(0)
            else:
                nWidgetsVbox = self.vbox1.count()
                for i in range(nWidgetsVbox):
                    if self.vbox1.itemAt(i) is not None:
                        if hasattr(self.vbox1.itemAt(i).widget(), 'form_name'):
                            if self.vbox1.itemAt(i).widget().form_name.text() == group_name:
                                self.groups_list.remove(self.vbox1.itemAt(i).widget())   # deletes list item
                                self.vbox1.itemAt(i).widget().setParent(None)            # deletes widget
                                self.combo2.removeItem(self.combo2.findText(group_name))
                                self.combo2.setCurrentIndex(0)
                                self.refresh_children()

    def is_referenced(self, grp_unique_name):
        """Tests if a group is being referenced any other groups. Returns boolean."""
        nWidgetsVbox = self.vbox1.count()
        for i in range(nWidgetsVbox):
            if self.vbox1.itemAt(i).widget() is not None:
                other_grp = self.vbox1.itemAt(i).widget()
                # check if this subgroup has any ComboBox referencing grp_unique_name
                for ch in other_grp.children():
                    if isinstance(ch, (CustomComboBox, QComboBox)):
                        if ch.currentText() == grp_unique_name:
                            return True
        return False

    def refresh_children(self, metadata=None):
        """Refreshes references with existing objects in child groups."""
        for child in self.groups_list:
            child.refresh_objects_references(metadata=metadata)

    def refresh_del_combo(self):
        """Refreshes del combobox with existing objects names in child groups."""
        self.combo2.clear()
        self.combo2.addItem('-- Del group --')
        for child in self.groups_list:
            self.combo2.addItem(child.form_name.text())
        self.refresh_children()

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        error = None
        data = {}
        # group_type counts, if there are multiple groups of same type, they are saved in a list
        grp_types = [grp.group_type for grp in self.groups_list]
        grp_type_count = {value: len(list(freq)) for value, freq in groupby(sorted(grp_types))}
        # initiate lists as values for groups keys with count > 1
        for k, v in grp_type_count.items():
            if v > 1 or k in ['Device', 'OpticalChannel', 'ImagingPlane', 'FRET']:
                data[k] = []
        # iterate over existing groups and copy their metadata
        for grp in self.groups_list:
            if grp_type_count[grp.group_type] > 1 or grp.group_type in ['Device', 'OpticalChannel', 'ImagingPlane', 'FRET']:
                data[grp.group_type].append(grp.read_fields())
            else:
                data[grp.group_type] = grp.read_fields()
        return data, error


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
