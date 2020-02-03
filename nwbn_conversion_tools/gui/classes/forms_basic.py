from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                             QGroupBox, QComboBox, QCheckBox, QMessageBox)
from PySide2.QtGui import QIntValidator, QDoubleValidator
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox

import pynwb


class BasicFormCollapsible(CollapsibleBox):
    def __init__(self, parent, pynwb_class, metadata=None):
        """Basic Groupbox filling form."""
        super().__init__(title=pynwb_class.__name__, parent=parent)
        self.parent = parent
        self.group_type = pynwb_class.__name__
        self.metadata = metadata
        self.pynwb_class = pynwb_class
        self.groups_list = []

        self.validator_float = QDoubleValidator()
        self.basic_forms()
        self.specific_forms()

    def basic_forms(self):
        """ Initializes forms."""
        # Forms grid, where each row: [label: form]
        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)

        # Loops through list of fields to create a form entry for each type
        self.fields = self.pynwb_class.__init__.__docval__['args']
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
            elif field['type'] in ('float', float):
                form = QLineEdit('')
                form.setValidator(self.validator_float)
            # hdmf/pynwb classes
            # elif type(field['type']).__module__ == '':
            #     form = field['type'](
            #         parent=,
            #         pynwb_class=,
            #     )
                #     self.lbl_donor = QLabel('donor:')
                #     self.donor_layout = QVBoxLayout()
                #     self.donor = QGroupBox()
                #     self.donor.setLayout(self.donor_layout)
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

    def specific_forms(self):
        print('this needs to be implemented by the child class')

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        # self.combo_device.clear()
        # for grp in self.parent.groups_list:
        #     if isinstance(grp, GroupDevice):
        #         self.combo_device.addItem(grp.lin_name.text())
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        metadata = {}
        n_fields = self.grid.rowCount()
        for i in range(n_fields):
            # Get field name
            name = self.grid.itemAtPosition(i, 0).widget().text()
            if '<' in name:
                name = name.split('<')[0]
            if ':' in name:
                name = name.replace(':', '')
            # Get field values
            group = self.grid.itemAtPosition(i, 2).widget()
            if isinstance(group, QLineEdit):
                try:
                    metadata[name] = float(group.text())
                except:
                    metadata[name] = group.text()
            if isinstance(group, QComboBox):
                metadata[name] = str(group.currentText())
            if isinstance(group, QGroupBox):
                metadata[name] = []
                for ii in range(group.children()[0].count()):
                    item = group.children()[0].itemAt(ii).widget()
                    metadata[name].append(item.read_fields())
        print(metadata)
        return metadata

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        pass
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
        # self.setContentLayout(self.grid)



class BasicFormFixed(QGroupBox):
    def __init__(self, parent, pynwb_class, metadata=None):
        """Basic Groupbox filling form."""
        super().__init__()
        self.parent = parent
        self.group_type = pynwb_class.__name__
        self.setTitle(self.group_type)
        self.metadata = metadata
        self.pynwb_class = pynwb_class
        self.groups_list = []

        self.validator_float = QDoubleValidator()
        self.basic_forms()
        self.specific_forms()

    def basic_forms(self):
        """ Initializes forms."""
        # Forms grid, where each row: [label: form]
        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)

        # Loops through list of fields to create a form entry for each type
        self.fields = self.pynwb_class.__init__.__docval__['args']
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
            elif field['type'] in ('float', float):
                form = QLineEdit('')
                form.setValidator(self.validator_float)
            else:
                continue

            lbl = QLabel(field_label)
            setattr(self, 'lbl_' + field['name'], lbl)
            setattr(self, 'form_' + field['name'], form)
            getattr(self, 'form_' + field['name']).setToolTip(field['doc'])

            self.grid.addWidget(getattr(self, 'lbl_' + field['name']), ii, 0, 1, 2)
            self.grid.addWidget(getattr(self, 'form_' + field['name']), ii, 2, 1, 4)
            ii += 1
        self.setLayout(self.grid)

    def specific_forms(self):
        print('this needs to be implemented by the child class')

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        metadata = {}
        n_fields = self.grid.rowCount()
        for i in range(n_fields):
            # Get field name
            name = self.grid.itemAtPosition(i, 0).widget().text()
            if '<' in name:
                name = name.split('<')[0]
            if ':' in name:
                name = name.replace(':', '')
            # Get field values
            group = self.grid.itemAtPosition(i, 2).widget()
            if isinstance(group, QLineEdit):
                try:
                    metadata[name] = float(group.text())
                except:
                    metadata[name] = group.text()
            if isinstance(group, QComboBox):
                metadata[name] = str(group.currentText())
            if isinstance(group, QGroupBox):
                metadata[name] = []
                for ii in range(group.children()[0].count()):
                    item = group.children()[0].itemAt(ii).widget()
                    metadata[name].append(item.read_fields())
        return metadata

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        pass
