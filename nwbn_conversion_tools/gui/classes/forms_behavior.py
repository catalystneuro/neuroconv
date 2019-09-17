from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QComboBox,
    QCheckBox, QFileDialog, QStyle)
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from nwbn_conversion_tools.gui.classes.forms_misc import GroupIntervalSeries
from nwbn_conversion_tools.gui.classes.forms_base import GroupTimeSeries
from datetime import datetime
import numpy as np
import yaml
import os




class GroupSpatialSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.SpatialSeries fields filling form."""
        super().__init__()
        self.setTitle('SpatialSeries')
        self.parent = parent
        self.group_name = 'SpatialSeries'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('SpatialSeries')
        self.lin_name.setToolTip("The name of this SpatialSeries dataset.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupSpatialSeries):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('SpatialSeries'+str(nInstances))

        self.lbl_data = QLabel('data:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(True)
        self.chk_data.setToolTip("The data this SpatialSeries dataset stores.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_reference_frame = QLabel('reference_frame:')
        self.lin_reference_frame = QLineEdit('reference frame')
        self.lin_reference_frame.setToolTip("Description defining what the zero-position is")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to "
            "convert to meters")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
        self.lin_resolution.setToolTip("The smallest meaningful difference (in "
            "specified unit) between values in data")

        self.lbl_timestamps = QLabel('timestamps:')
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip("Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_starting_time = QLabel('starting_time:')
        self.lin_starting_time = QLineEdit('')
        self.lin_starting_time.setPlaceholderText("0.0")
        self.lin_starting_time.setToolTip("The timestamp of the first sample")

        self.lbl_rate = QLabel('rate:')
        self.lin_rate = QLineEdit('')
        self.lin_rate.setPlaceholderText("0.0")
        self.lin_rate.setToolTip("Sampling rate in Hz")

        self.lbl_comments = QLabel('comments:')
        self.lin_comments = QLineEdit('')
        self.lin_comments.setPlaceholderText("comments")
        self.lin_comments.setToolTip("Human-readable comments about this SpatialSeries dataset")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this SpatialSeries dataset")

        self.lbl_control = QLabel('control:')
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip("Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_control_description = QLabel('control_description:')
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip("Description of each control value.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_reference_frame, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_reference_frame, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 6, 0, 1, 2)
        self.grid.addWidget(self.lin_starting_time, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_rate, 7, 0, 1, 2)
        self.grid.addWidget(self.lin_rate, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_comments, 8, 0, 1, 2)
        self.grid.addWidget(self.lin_comments, 8, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 9, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 10, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 10, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 11, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 11, 2, 1, 2)
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
        data['reference_frame'] = self.lin_reference_frame.text()
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except:
            pass
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except:
            pass
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        try:
            data['starting_time'] = float(self.lin_starting_time.text())
        except:
            pass
        try:
            data['rate'] = float(self.lin_rate.text())
        except:
            pass
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
        self.lin_reference_frame.setText(data['reference_frame'])
        if 'conversion' in data:
            self.lin_conversion.setText(str(data['conversion']))
        if 'resolution' in data:
            self.lin_resolution.setText(str(data['resolution']))
        if 'timestamps' in data:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in data:
            self.lin_starting_time.setText(str(data['starting_time']))
        if 'rate' in data:
            self.lin_rate.setText(str(data['rate']))
        if 'comments' in data:
            self.lin_comments.setText(data['comments'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)



class GroupBehavioralEpochs(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.BehavioralEpochs fields filling form."""
        super().__init__()
        self.setTitle('BehavioralEpochs')
        self.parent = parent
        self.group_name = 'BehavioralEpochs'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('BehavioralEpochs')
        self.lin_name.setToolTip("The unique name of this BehavioralEpochs")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupBehavioralEpochs):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('BehavioralEpochs'+str(nInstances))

        self.lbl_interval_series = QLabel('interval_series:')
        self.combo_interval_series = CustomComboBox()
        self.combo_interval_series.setToolTip("IntervalSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_interval_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_interval_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_interval_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupIntervalSeries):
                self.combo_interval_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['interval_series'] = self.combo_interval_series.currentText()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_interval_series.clear()
        self.combo_interval_series.addItem(data['interval_series'])




class GroupBehavioralEvents(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.BehavioralEvents fields filling form."""
        super().__init__()
        self.setTitle('BehavioralEvents')
        self.parent = parent
        self.group_name = 'BehavioralEvents'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('BehavioralEvents')
        self.lin_name.setToolTip("The unique name of this BehavioralEvents")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupBehavioralEvents):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('BehavioralEvents'+str(nInstances))

        self.lbl_time_series = QLabel('time_series:')
        self.combo_time_series = CustomComboBox()
        self.combo_time_series.setToolTip("TimeSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_time_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_time_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_time_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupTimeSeries):
                self.combo_time_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['time_series'] = self.combo_time_series.currentText()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_time_series.clear()
        self.combo_time_series.addItem(data['time_series'])





class GroupCustomExample(QGroupBox):
    def __init__(self, parent):
        """
        Groupbox for to serve as example for creation of custom groups.
        Don't forget to add this class to the relevant handling functions at the
        parent, e.g. add_group()
        """
        super().__init__()
        self.setTitle('CustomName')
        self.parent = parent
        self.group_name = 'CustomName'

        # Name: it has a special treatment, since it need to be unique we test
        # if the parent contain other objects of the same type
        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('CustomName')
        self.lin_name.setToolTip("The unique name of this group.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupCustomExample):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('CustomName'+str(nInstances))

        # Mandatory field: we fill it with default values
        self.lbl_mandatory = QLabel('mandatory:')
        self.lin_mandatory = QLineEdit('ABC123')
        self.lin_mandatory.setToolTip("This is a mandatory field.")

        # Optional field: we leave a placeholder text as example
        self.lbl_optional = QLabel('optional:')
        self.lin_optional = QLineEdit('')
        self.lin_optional.setPlaceholderText("example")
        self.lin_optional.setToolTip("This is an optional field.")

        # Field with link to other objects. This type of field needs to be
        # updated with self.refresh_objects_references()
        self.lbl_link = QLabel('link:')
        self.combo_link = CustomComboBox()
        self.combo_link.setToolTip("This field links to existing objects.")

        # Field that should be handled by conversion script
        self.lbl_script = QLabel('script:')
        self.chk_script = QCheckBox("Get from source file")
        self.chk_script.setChecked(False)
        self.chk_script.setToolTip("This field will be handled by conversion script.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_mandatory, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_mandatory, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_optional, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_optional, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_link, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_link, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_script, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_script, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_link.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCustomExample):
                self.combo_link.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['mandatory'] = self.lin_mandatory.text()
        data['optional'] = self.lin_optional.text()
        data['link'] = self.combo_link.currentText()
        if self.chk_script.isChecked():
            data['script'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_mandatory.setText(data['mandatory'])
        if 'optional' in data:
            self.lin_optional.setText(data['optional'])
        self.combo_link.clear()
        self.combo_link.addItem(data['link'])
        if 'script' in data:
            self.chk_script.setChecked(True)




class GroupBehavior(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Behavior modules fields filling forms."""
        super().__init__()
        self.setTitle('Behavior')
        self.group_name = 'Behavior'
        self.groups_list = []

        self.combo1 = CustomComboBox()
        self.combo1.addItem('-- Add group --')
        self.combo1.addItem('Device')
        self.combo1.addItem('IntervalSeries')
        self.combo1.addItem('TimeSeries')
        self.combo1.addItem('SpatialSeries')
        self.combo1.addItem('BehavioralEpochs')
        self.combo1.addItem('BehavioralEvents')
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
        elif group_type == 'IntervalSeries':
            item = GroupIntervalSeries(self)
        elif group_type == 'TimeSeries':
            item = GroupTimeSeries(self)
        elif group_type == 'SpatialSeries':
            item = GroupSpatialSeries(self)
        elif group_type == 'BehavioralEpochs':
            item = GroupBehavioralEpochs(self)
        elif group_type =='BehavioralEvents':
            item = GroupBehavioralEvents(self)
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
