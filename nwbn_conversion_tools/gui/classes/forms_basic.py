from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                             QGroupBox, QComboBox, QCheckBox, QMessageBox)
from PySide2.QtGui import QIntValidator, QDoubleValidator
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox

import pynwb


name_class_reference = {
    'NWBFile': pynwb.file.NWBFile,
    'Subject': pynwb.file.Subject,
    'ImagingPlane': pynwb.ophys.ImagingPlane,
}


class BasicForm(CollapsibleBox):
    def __init__(self, parent, type, metadata=None):
        """Basic Groupbox filling form."""
        super().__init__(title=type, parent=parent)
        #self.setTitle(title)
        self.parent = parent
        self.group_type = type
        self.metadata = metadata
        self._pynwb_class = name_class_reference[self.group_type]

        self.validator_float = QDoubleValidator()
        self.init_forms()

    def init_forms(self):
        """ Initializes forms."""
        # Forms grid, where each row: [label: form]
        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)

        # Loops through list of fields to create a form entry for each type
        self.fields = self._pynwb_class.__init__.__docval__['args']
        ii = 0
        for field in self.fields:
            # Required fields get a red star in their label
            if 'default' not in field:
                required = True
                field_label = field['name'] + "<span style='color:"+required_asterisk_color+";'>*</span>:"
            # Optional fields
            else:
                required = False
                field_label = field['name'] + ":"

            # String types
            if field['type'] is str:
                form = QLineEdit('')
            # Float types
            elif field['type'] is 'float':
                form = QLineEdit('')
                form.setValidator(self.validator_float)
            # Skip data types, continue looping
            else:
                continue

            lbl = QLabel(field_label)
            setattr(self, 'lbl_' + field['name'], lbl)
            setattr(self, 'form_' + field['name'], form)
            getattr(self, 'form_' + field['name']).setToolTip(field['doc'])

            self.grid.addWidget(getattr(self, 'lbl_' + field['name']), ii, 0, 1, 2)
            self.grid.addWidget(getattr(self, 'form_' + field['name']), ii, 2, 1, 4)
            ii += 1
        self.setContentLayout(self.grid)

        # TO BE SUBSTITUTED ------------------------------------------------------
        # self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        # self.lin_name = QLineEdit('ImagingPlane')
        # self.lin_name.setToolTip("The name of this ImagingPlane")
        #
        # self.lbl_optical_channel = QLabel('optical_channel<span style="color:'+required_asterisk_color+';">*</span>:')
        # self.optical_channel_layout = QVBoxLayout()
        # self.optical_channel = QGroupBox()
        # self.optical_channel.setLayout(self.optical_channel_layout)
        # self.optical_channel.setToolTip(
        #     "One of possibly many groups storing channels pecific data")
        #
        #
        # self.lbl_device = QLabel('device<span style="color:'+required_asterisk_color+';">*</span>:')
        # self.combo_device = CustomComboBox()
        # self.combo_device.setToolTip("The device that was used to record")
        #
        # self.lbl_excitation_lambda = QLabel('excitation_lambda<span style="color:'+required_asterisk_color+';">*</span>:')
        # self.lin_excitation_lambda = QLineEdit('0.0')
        # self.lin_excitation_lambda.setToolTip("Excitation wavelength in nm")
        #
        # self.lbl_manifold = QLabel('manifold:')
        # self.chk_manifold = QCheckBox("Get from source file")
        # self.chk_manifold.setChecked(False)
        # self.chk_manifold.setToolTip(
        #     "Physical position of each pixel. size=(height, width, xyz).\n "
        #     "Check box if this data will be retrieved from source file.\n"
        #     "Uncheck box to ignore it.")
        #
        # self.lbl_conversion = QLabel('conversion:')
        # self.lin_conversion = QLineEdit('')
        # self.lin_conversion.setPlaceholderText("1")
        # self.lin_conversion.setToolTip(
        #     "Multiplier to get from stored values to specified unit (e.g., 1e-3 for millimeters)")


    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_device.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupDevice):
                self.combo_device.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        metadata = {}
        # data['name'] = self.lin_name.text()
        # data['optical_channel'] = []
        # nItems = self.optical_channel_layout.count()
        # for i in range(nItems):
        #     item = self.optical_channel_layout.itemAt(i).widget()
        #     data['optical_channel'].append(item.read_fields())
        # data['description'] = self.lin_description.text()
        # data['device'] = str(self.combo_device.currentText())
        # try:
        #     data['excitation_lambda'] = float(self.lin_excitation_lambda.text())
        # except ValueError as error:
        #     print(error)
        #     data['excitation_lambda'] = 0.0
        # try:
        #     data['imaging_rate'] = float(self.lin_imaging_rate.text())
        # except ValueError as error:
        #     print(error)
        #     data['imaging_rate'] = 0.0
        # data['indicator'] = self.lin_indicator.text()
        # data['location'] = self.lin_location.text()
        # if self.chk_manifold.isChecked():
        #     data['manifold'] = True
        # try:
        #     data['conversion'] = float(self.lin_conversion.text())
        # except ValueError as error:
        #     print(error)
        #     data['conversion'] = 0.0
        # data['unit'] = self.lin_unit.text()
        # data['reference_frame'] = self.lin_reference_frame.text()
        return metadata

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        # if field['name'] in metadata:
        #     form_placeholder = metadata[field['name']]
        # else:
        #     form_placeholder = "ADDME"

        # self.lin_name.setText(data['name'])
        # nItems = self.optical_channel_layout.count()
        # for ind, sps in enumerate(data['optical_channel']):
        #     if ind >= nItems:
        #         item = GroupOpticalChannel(self, metadata=data['optical_channel'][ind])
        #         self.optical_channel_layout.addWidget(item)
        # if 'description' in data:
        #     self.lin_description.setText(data['description'])
        # self.combo_device.clear()
        # self.combo_device.addItem(data['device'])
        # self.lin_excitation_lambda.setText(str(data['excitation_lambda']))
        # self.lin_imaging_rate.setText(str(data['imaging_rate']))
        # self.lin_indicator.setText(str(data['indicator']))
        # self.lin_location.setText(str(data['location']))
        # if 'manifold' in data:
        #     self.chk_manifold.setChecked(True)
        # if 'conversion' in data:
        #     self.lin_conversion.setText(str(data['conversion']))
        # if 'unit' in data:
        #     self.lin_unit.setText(data['unit'])
        # if 'reference_frame' in data:
        #     self.lin_reference_frame.setText(data['reference_frame'])
        self.setContentLayout(self.grid)
