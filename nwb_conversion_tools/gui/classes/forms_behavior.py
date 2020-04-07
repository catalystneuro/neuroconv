from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                               QGroupBox, QComboBox, QMessageBox)
from nwb_conversion_tools.gui.utils.configs import required_asterisk_color
from nwb_conversion_tools.gui.classes.forms_misc import GroupIntervalSeries
from nwb_conversion_tools.gui.classes.forms_base import GroupTimeSeries
from nwb_conversion_tools.gui.classes.forms_basic import BasicFormCollapsible, BasicFormFixed
import pynwb
from itertools import groupby


class GroupSpatialSeries(BasicFormFixed):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.SpatialSeries fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.behavior.SpatialSeries, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        pass


class GroupBehavioralEpochs(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.BehavioralEpochs fields filling form."""
        super().__init__()
        self.setTitle('BehavioralEpochs')
        self.parent = parent
        self.group_type = 'BehavioralEpochs'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('BehavioralEpochs')
        self.form_name.setToolTip("The unique name of this BehavioralEpochs")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupBehavioralEpochs):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('BehavioralEpochs'+str(nInstances))

        self.lbl_interval_series = QLabel('interval_series:')
        self.interval_series = GroupIntervalSeries(self)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_interval_series, 1, 0, 1, 2)
        self.grid.addWidget(self.interval_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['interval_series'] = self.interval_series.read_fields()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])


class GroupBehavioralEvents(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.BehavioralEvents fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.behavior.BehavioralEvents, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'time_series',
             'type': 'group',
             'class': 'TimeSeries',
             'required': True,
             'doc': 'TimeSeries to store in this interface'},
        ]
        self.fields_info.extend(specific_fields)


class GroupBehavioralTimeSeries(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.BehavioralTimeSeries fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.behavior.BehavioralTimeSeries, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'time_series',
             'type': 'group',
             'class': 'TimeSeries',
             'required': True,
             'doc': 'TimeSeries to store in this interface'},
        ]
        self.fields_info.extend(specific_fields)


class GroupPupilTracking(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.PupilTracking fields filling form."""
        super().__init__()
        self.setTitle('PupilTracking')
        self.parent = parent
        self.group_type = 'PupilTracking'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('PupilTracking')
        self.form_name.setToolTip("The unique name of this PupilTracking")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupPupilTracking):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('PupilTracking'+str(nInstances))

        self.lbl_time_series = QLabel('time_series:')
        self.time_series = GroupTimeSeries(self)
        # self.combo_time_series = CustomComboBox()
        # self.combo_time_series.setToolTip("TimeSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_time_series, 1, 0, 1, 2)
        self.grid.addWidget(self.time_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['time_series'] = self.time_series.read_fields()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])


class GroupEyeTracking(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.EyeTracking fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.behavior.EyeTracking, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'spatial_series',
             'type': 'group',
             'class': 'SpatialSeries',
             'required': True,
             'doc': 'SpatialSeries to store in this interface'},
        ]
        self.fields_info.extend(specific_fields)


class GroupCompassDirection(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.CompassDirection fields filling form."""
        super().__init__()
        self.setTitle('CompassDirection')
        self.parent = parent
        self.group_type = 'CompassDirection'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('CompassDirection')
        self.form_name.setToolTip("The unique name of this CompassDirection")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupCompassDirection):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('CompassDirection'+str(nInstances))

        self.lbl_spatial_series = QLabel('spatial_series:')
        self.spatial_series = GroupSpatialSeries(self)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_spatial_series, 1, 0, 1, 2)
        self.grid.addWidget(self.spatial_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['spatial_series'] = self.spatial_series.read_fields()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])


class GroupPosition(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.Position fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.behavior.Position, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'spatial_series',
             'type': 'group',
             'class': 'SpatialSeries',
             'required': True,
             'doc': 'SpatialSeries to store in this interface'},
        ]
        self.fields_info.extend(specific_fields)


class GroupBehavior(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Behavior modules fields filling forms."""
        super().__init__()
        self.setTitle('Behavior')
        self.group_type = 'Behavior'
        self.groups_list = []

        self.combo1 = CustomComboBox()
        self.combo1.addItem('-- Add group --')
        self.combo1.addItem('Device')
        self.combo1.addItem('IntervalSeries')
        self.combo1.addItem('TimeSeries')
        self.combo1.addItem('SpatialSeries')
        self.combo1.addItem('BehavioralEpochs')
        self.combo1.addItem('BehavioralEvents')
        self.combo1.addItem('BehavioralTimeSeries')
        self.combo1.addItem('PupilTracking')
        self.combo1.addItem('EyeTracking')
        self.combo1.addItem('CompassDirection')
        self.combo1.addItem('Position')
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
        self.vbox1.insertWidget(nWidgetsVbox - 1, group)  # insert before the stretch
        self.combo1.setCurrentIndex(0)
        # self.combo2.addItem(group.form_name.text())
        self.refresh_children(metadata=metadata)

    def del_group(self, group_name):
        """Deletes group form by name."""
        if group_name == 'combo':
            group_name = str(self.combo2.currentText())
        if group_name != '-- Del group --':
            # Tests if any other group references this one
            if self.is_referenced(grp_unique_name=group_name):
                QMessageBox.warning(self, "Cannot delete subgroup",
                                    group_name + " is being referenced by another subgroup(s).\n"
                                    "You should remove any references of " + group_name + " before "
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
            if v > 1 or k in ['Device', 'TimeSeries', 'SpatialSeries']:
                data[k] = []
        # iterate over existing groups and copy their metadata
        for grp in self.groups_list:
            if grp_type_count[grp.group_type] > 1 or grp.group_type in ['Device', 'TimeSeries', 'SpatialSeries']:
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
