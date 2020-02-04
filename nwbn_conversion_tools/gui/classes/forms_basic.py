# Basic classes for forms creation, writing and reading
#
# GUI forms take 3 formats:
# QLineEdit - for strings and floats (e.g. 'name' and 'rate')
# QComboBox - for links (e.g. 'device')
# QGroupBox - for groups (e.g. 'optical_channel')
#
# The self.fields_info list take dictionaries with the key/value pairs:
# 'name': name of the field
# 'type': 'str', 'float', 'link' or 'group'
# 'class': the pynwb class of this field, valid only for 'link' and 'group' types
# 'required': whether it is a required or an optional field
# 'doc': description of the field
# ------------------------------------------------------------------------------
from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                               QGroupBox, QComboBox)
from PySide2.QtGui import QDoubleValidator

from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.utils.name_references import name_to_gui_class
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox

from collections.abc import Iterable


class BasicFormCollapsible(CollapsibleBox):
    def __init__(self, parent, pynwb_class, metadata=None):
        """Basic Groupbox filling form."""
        super().__init__(title=pynwb_class.__name__, parent=parent)
        self.parent = parent
        self.group_type = pynwb_class.__name__
        self.metadata = metadata
        self.pynwb_class = pynwb_class
        self.groups_list = []

        self.fill_fields_info()
        self.fields_info_update()
        self.make_forms()

    def fill_fields_info(self):
        """Fills the fields info details dictionary."""
        # Loops through list of fields from class and store info in dictionary
        self.fields = self.pynwb_class.__init__.__docval__['args']
        self.fields_info = []
        for field in self.fields:
            # Required fields get a red star in their label
            if 'default' not in field:
                required = True
            # Optional fields
            else:
                required = False

            # Skip data types, continue looping
            if 'shape' in field:
                continue
            # Skip Iterable type, continue looping
            if field['type'] == Iterable:
                continue
            # String types
            if field['type'] is str:
                self.fields_info.append({
                    'name': field['name'],
                    'type': 'str',
                    'class': None,
                    'required': required,
                    'doc': field['doc']
                })
            # Float types
            elif field['type'] in ('float', float):
                self.fields_info.append({
                    'name': field['name'],
                    'type': 'float',
                    'class': None,
                    'required': required,
                    'doc': field['doc']
                })

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        pass

    def make_forms(self):
        """ Initializes forms."""
        # Forms grid, where each row: [label: form]
        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        validator_float = QDoubleValidator()

        # Loops through fields info to create a form entry for each
        for ii, field in enumerate(self.fields_info):
            # Required fields get a red star in their label
            if field['required']:
                field_label = field['name'] + "<span style='color:"+required_asterisk_color+";'>*</span>:"
            else:
                field_label = field['name'] + ":"

            # String types
            if field['type'] == 'str':
                form = QLineEdit('')
            # Float types
            elif field['type'] == 'float':
                form = QLineEdit('')
                form.setValidator(validator_float)
            # Link types
            elif field['type'] == 'link':
                form = CustomComboBox()
            # Group types
            elif field['type'] == 'group':
                setattr(self, field['name'] + '_layout', QVBoxLayout())
                form = QGroupBox()
                form.setLayout(getattr(self, field['name'] + '_layout'))

            lbl = QLabel(field_label)
            setattr(self, 'lbl_' + field['name'], lbl)
            setattr(self, 'form_' + field['name'], form)
            getattr(self, 'form_' + field['name']).setToolTip(field['doc'])

            self.grid.addWidget(getattr(self, 'lbl_' + field['name']), ii, 0, 1, 2)
            self.grid.addWidget(getattr(self, 'form_' + field['name']), ii, 2, 1, 4)

    def refresh_objects_references(self, metadata=None):
        """
        Refreshes references with existing objects in parent / grandparent groups.
        Refreshes children's references.
        """
        # Refreshes self comboboxes
        for field in self.fields_info:
            if field['type'] == 'link':
                form = getattr(self, 'form_' + field['name'])
                form.clear()
                form_gui_class = name_to_gui_class[field['class']]
                # Search through parent
                for grp in self.parent.groups_list:
                    # Adds existing specfic groups to combobox
                    if isinstance(grp, form_gui_class):
                        getattr(self, 'form_' + field['name']).addItem(grp.form_name.text())
                # Search through grandparent
                for grp in self.parent.parent.groups_list:
                    # Adds existing specfic groups to combobox
                    if isinstance(grp, form_gui_class):
                        getattr(self, 'form_' + field['name']).addItem(grp.form_name.text())
        # Refreshes children
        for child in self.groups_list:
            child.refresh_objects_references(metadata=metadata)

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
        # Loops through fields info list
        for i, field in enumerate(self.fields_info):
            # Write metadata to field
            if field['name'] in metadata:
                group = self.grid.itemAtPosition(i, 2).widget()
                # If field form is a string or float
                if isinstance(group, QLineEdit):
                    group.setText(str(metadata[field['name']]))
                # If field form is a link
                if isinstance(group, QComboBox):
                    group.clear()
                    group.addItem(str(metadata[field['name']]))
                # If field form is a group
                if isinstance(group, QGroupBox):
                    n_items = group.children()[0].count()
                    for ind, sps in enumerate(metadata[field['name']]):
                        if ind >= n_items:
                            item_class = name_to_gui_class[field['class']]
                            item = item_class(self, metadata={})
                            item.write_fields(metadata=metadata[field['name']][ind])
                            self.groups_list.append(item)
                            getattr(self, field['name'] + '_layout').addWidget(item)
        self.setContentLayout(self.grid)


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

        self.fill_fields_info()
        self.fields_info_update()
        self.make_forms()

    def fill_fields_info(self):
        """Fills the fields info details dictionary."""
        # Loops through list of fields from class and store info in dictionary
        self.fields = self.pynwb_class.__init__.__docval__['args']
        self.fields_info = []
        for field in self.fields:
            # Required fields get a red star in their label
            if 'default' not in field:
                required = True
            # Optional fields
            else:
                required = False

            # Skip data types, continue looping
            if 'shape' in field:
                continue
            # Skip Iterable type, continue looping
            if field['type'] == Iterable:
                continue
            # String types
            if field['type'] is str:
                self.fields_info.append({
                    'name': field['name'],
                    'type': 'str',
                    'class': None,
                    'required': required,
                    'doc': field['doc']
                })
            # Float types
            elif field['type'] in ('float', float):
                self.fields_info.append({
                    'name': field['name'],
                    'type': 'float',
                    'class': None,
                    'required': required,
                    'doc': field['doc']
                })

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        pass

    def make_forms(self):
        """ Initializes forms."""
        # Forms grid, where each row: [label: form]
        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        validator_float = QDoubleValidator()

        # Loops through fields info to create a form entry for each
        for ii, field in enumerate(self.fields_info):
            # Required fields get a red star in their label
            if field['required']:
                field_label = field['name'] + "<span style='color:"+required_asterisk_color+";'>*</span>:"
            else:
                field_label = field['name'] + ":"

            # String types
            if field['type'] == 'str':
                form = QLineEdit('')
            # Float types
            elif field['type'] == 'float':
                form = QLineEdit('')
                form.setValidator(validator_float)
            # Link types
            elif field['type'] == 'link':
                form = CustomComboBox()
            # Group types
            elif field['type'] == 'group':
                setattr(self, field['name'] + '_layout', QVBoxLayout())
                form = QGroupBox()
                form.setLayout(getattr(self, field['name'] + '_layout'))

            lbl = QLabel(field_label)
            setattr(self, 'lbl_' + field['name'], lbl)
            setattr(self, 'form_' + field['name'], form)
            getattr(self, 'form_' + field['name']).setToolTip(field['doc'])

            self.grid.addWidget(getattr(self, 'lbl_' + field['name']), ii, 0, 1, 2)
            self.grid.addWidget(getattr(self, 'form_' + field['name']), ii, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """
        Refreshes references with existing objects in parent / grandparent groups.
        Refreshes children's references.
        """
        # Refreshes self comboboxes
        for field in self.fields_info:
            if field['type'] == 'link':
                form = getattr(self, 'form_' + field['name'])
                form.clear()
                form_gui_class = name_to_gui_class[field['class']]
                # Search through parent
                for grp in self.parent.groups_list:
                    # Adds existing specfic groups to combobox
                    if isinstance(grp, form_gui_class):
                        getattr(self, 'form_' + field['name']).addItem(grp.form_name.text())
                # Search through grandparent
                for grp in self.parent.parent.groups_list:
                    # Adds existing specfic groups to combobox
                    if isinstance(grp, form_gui_class):
                        getattr(self, 'form_' + field['name']).addItem(grp.form_name.text())
        # Refreshes children
        for child in self.groups_list:
            child.refresh_objects_references(metadata=metadata)

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
        # Loops through fields info list
        for i, field in enumerate(self.fields_info):
            # Write metadata to field
            if field['name'] in metadata:
                group = self.grid.itemAtPosition(i, 2).widget()
                # If field form is a string or float
                if isinstance(group, QLineEdit):
                    group.setText(str(metadata[field['name']]))
                # If field form is a link
                if isinstance(group, QComboBox):
                    group.clear()
                    group.addItem(str(metadata[field['name']]))
                # If field form is a group
                if isinstance(group, QGroupBox):
                    n_items = group.children()[0].count()
                    for ind, sps in enumerate(metadata[field['name']]):
                        if ind >= n_items:
                            item_class = name_to_gui_class[field['class']]
                            item = item_class(self, metadata={})
                            item.write_fields(metadata=metadata[field['name']][ind])
                            self.groups_list.append(item)
                            getattr(self, field['name'] + '_layout').addWidget(item)
        self.setLayout(self.grid)


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
