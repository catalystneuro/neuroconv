from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                             QGroupBox, QComboBox, QCheckBox, QMessageBox)
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from nwbn_conversion_tools.gui.classes.forms_misc import GroupIntervalSeries
from nwbn_conversion_tools.gui.classes.forms_base import GroupTimeSeries
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox
from itertools import groupby


class GroupSpatialSeries(QGroupBox):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.behavior.SpatialSeries fields filling form."""
        super().__init__()
        self.setTitle('SpatialSeries')
        self.parent = parent
        self.group_type = 'SpatialSeries'
        if metadata is None:
            metadata = dict()

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'name' in metadata:
            self.form_name = QLineEdit(metadata['name'])
        else:
            self.form_name = QLineEdit('SpatialSeries')
        self.form_name.setToolTip("The name of this SpatialSeries dataset.")

        self.lbl_reference_frame = QLabel('reference_frame<span style="color:'+required_asterisk_color+';">*</span>:')
        if 'reference_frame' in metadata:
            self.form_reference_frame = QLineEdit(metadata['reference_frame'])
        else:
            self.form_reference_frame = QLineEdit('reference frame')
        self.form_reference_frame.setToolTip("Description defining what the zero-position is")

        self.lbl_conversion = QLabel('conversion:')
        if 'conversion' in metadata:
            self.form_conversion = QLineEdit(str(metadata['conversion']))
        else:
            self.form_conversion = QLineEdit('')
        self.form_conversion.setToolTip("Scalar to multiply each element by to convert to meters")

        self.lbl_resolution = QLabel('resolution:')
        if 'resolution' in metadata:
            self.form_resolution = QLineEdit(str(metadata['resolution']))
        else:
            self.form_resolution = QLineEdit('')
        self.form_resolution.setToolTip(
            "The smallest meaningful difference (in specified unit) between values in data")

        self.lbl_timestamps = QLabel('timestamps:')
        self.chk_timestamps = QCheckBox("Get from source file")
        if 'timestamps' in metadata:
            self.chk_timestamps.setChecked(metadata['timestamps'])
        else:
            self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_starting_time = QLabel('starting_time:')
        if 'starting_time' in metadata:
            self.form_starting_time = QLineEdit(str(metadata['starting_time']))
        else:
            self.form_starting_time = QLineEdit('')
        self.form_starting_time.setToolTip("The timestamp of the first sample")

        self.lbl_rate = QLabel('rate:')
        if 'rate' in metadata:
            self.form_rate = QLineEdit(str(metadata['rate']))
        else:
            self.form_rate = QLineEdit('')
        self.form_rate.setToolTip("Sampling rate in Hz")

        self.lbl_comments = QLabel('comments:')
        if 'comments' in metadata:
            self.form_comments = QLineEdit(metadata['comments'])
        else:
            self.form_comments = QLineEdit('')
        self.form_comments.setPlaceholderText("comments")
        self.form_comments.setToolTip("Human-readable comments about this SpatialSeries dataset")

        self.lbl_description = QLabel('description:')
        if 'description' in metadata:
            self.form_description = QLineEdit(metadata['description'])
        else:
            self.form_description = QLineEdit('')
        self.form_description.setPlaceholderText("description")
        self.form_description.setToolTip(" Description of this SpatialSeries dataset")

        self.lbl_control = QLabel('control:')
        self.chk_control = QCheckBox("Get from source file")
        if 'control' in metadata:
            self.chk_control.setChecked(metadata['control'])
        else:
            self.chk_control.setChecked(False)
        self.chk_control.setToolTip(
            "Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_control_description = QLabel('control_description:')
        self.chk_control_description = QCheckBox("Get from source file")
        if 'control_description' in metadata:
            self.chk_control_description.setChecked(metadata['control_description'])
        else:
            self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip(
            "Description of each control value.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_reference_frame, 2, 0, 1, 2)
        self.grid.addWidget(self.form_reference_frame, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 3, 0, 1, 2)
        self.grid.addWidget(self.form_conversion, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 4, 0, 1, 2)
        self.grid.addWidget(self.form_resolution, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 6, 0, 1, 2)
        self.grid.addWidget(self.form_starting_time, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_rate, 7, 0, 1, 2)
        self.grid.addWidget(self.form_rate, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_comments, 8, 0, 1, 2)
        self.grid.addWidget(self.form_comments, 8, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 9, 0, 1, 2)
        self.grid.addWidget(self.form_description, 9, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 10, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 10, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 11, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 11, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['reference_frame'] = self.form_reference_frame.text()
        try:
            data['conversion'] = float(self.form_conversion.text())
        except ValueError as error:
            print(error)
        try:
            data['resolution'] = float(self.form_resolution.text())
        except ValueError as error:
            print(error)
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        try:
            data['starting_time'] = float(self.form_starting_time.text())
        except ValueError as error:
            print(error)
        try:
            data['rate'] = float(self.form_rate.text())
        except ValueError as error:
            print(error)
        data['comments'] = self.form_comments.text()
        data['description'] = self.form_description.text()
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])
        self.form_reference_frame.setText(data['reference_frame'])
        if 'conversion' in data:
            self.form_conversion.setText(str(data['conversion']))
        if 'resolution' in data:
            self.form_resolution.setText(str(data['resolution']))
        if 'timestamps' in data:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in data:
            self.form_starting_time.setText(str(data['starting_time']))
        if 'rate' in data:
            self.form_rate.setText(str(data['rate']))
        if 'comments' in data:
            self.form_comments.setText(data['comments'])
        if 'description' in data:
            self.form_description.setText(data['description'])
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


#class GroupBehavioralEvents(QGroupBox):
class GroupBehavioralEvents(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.BehavioralEvents fields filling form."""
        super().__init__(title="BehavioralEvents", parent=parent)
        #self.setTitle('BehavioralEvents')
        self.parent = parent
        self.group_type = 'BehavioralEvents'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('BehavioralEvents')
        self.form_name.setToolTip("The unique name of this BehavioralEvents")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupBehavioralEvents):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('BehavioralEvents'+str(nInstances))

        self.lbl_time_series = QLabel('time_series:')
        self.time_series = GroupTimeSeries(self)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_time_series, 1, 0, 1, 2)
        self.grid.addWidget(self.time_series, 1, 2, 1, 4)
        #self.setLayout(self.grid)

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
        self.setContentLayout(self.grid)


class GroupBehavioralTimeSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.BehavioralTimeSeries fields filling form."""
        super().__init__()
        self.setTitle('BehavioralTimeSeries')
        self.parent = parent
        self.group_type = 'BehavioralTimeSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('BehavioralTimeSeries')
        self.form_name.setToolTip("The unique name of this BehavioralTimeSeries")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupBehavioralTimeSeries):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('BehavioralTimeSeries'+str(nInstances))

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


#class GroupEyeTracking(QGroupBox):
class GroupEyeTracking(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.EyeTracking fields filling form."""
        super().__init__(title="GroupEyeTracking", parent=parent)
        #self.setTitle('EyeTracking')
        self.parent = parent
        self.group_type = 'EyeTracking'
        self.groups_list = []

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('EyeTracking')
        self.form_name.setToolTip("The unique name of this EyeTracking")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupEyeTracking):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('EyeTracking'+str(nInstances))

        self.lbl_spatial_series = QLabel('spatial_series:')
        self.spatial_series_layout = QVBoxLayout() #GroupSpatialSeries(self)
        self.spatial_series = QGroupBox() #CollapsibleBox()
        self.spatial_series.setLayout(self.spatial_series_layout)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_spatial_series, 1, 0, 1, 2)
        self.grid.addWidget(self.spatial_series, 1, 2, 1, 4)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['spatial_series'] = []
        nItems = self.spatial_series_layout.count()
        for i in range(nItems):
            item = self.spatial_series_layout.itemAt(i).widget()
            data['spatial_series'].append(item.read_fields())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])
        nItems = self.spatial_series_layout.count()
        for ind, sps in enumerate(data['spatial_series']):
            if ind >= nItems:
                item = GroupSpatialSeries(self, metadata=data['spatial_series'][ind])
                self.spatial_series_layout.addWidget(item)
        self.setContentLayout(self.grid)


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


#class GroupPosition(QGroupBox):
class GroupPosition(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.behavior.Position fields filling form."""
        super().__init__(title="Position", parent=parent)
        #self.setTitle('Position')
        self.parent = parent
        self.group_type = 'Position'
        self.groups_list = []

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('Position')
        self.form_name.setToolTip("The unique name of this Position")

        self.lbl_spatial_series = QLabel('spatial_series:')
        self.spatial_series_layout = QVBoxLayout() #GroupSpatialSeries(self)
        self.spatial_series = QGroupBox() #CollapsibleBox()
        self.spatial_series.setLayout(self.spatial_series_layout)
        #self.spatial_series.setContentLayout(self.spatial_series_layout)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_spatial_series, 1, 0, 1, 2)
        self.grid.addWidget(self.spatial_series, 1, 2, 1, 4)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['spatial_series'] = []
        nItems = self.spatial_series_layout.count()
        for i in range(nItems):
            item = self.spatial_series_layout.itemAt(i).widget()
            data['spatial_series'].append(item.read_fields())
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])
        nItems = self.spatial_series_layout.count()
        for ind, sps in enumerate(data['spatial_series']):
            if ind >= nItems:
                item = GroupSpatialSeries(self, metadata=data['spatial_series'][ind])
                self.spatial_series_layout.addWidget(item)
        self.setContentLayout(self.grid)


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

    def add_group(self, group_type, metadata=None):
        """Adds group form."""
        if group_type == 'combo':
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
        elif group_type == 'BehavioralEvents':
            item = GroupBehavioralEvents(self)
        elif group_type == 'BehavioralTimeSeries':
            item = GroupBehavioralTimeSeries(self)
        elif group_type == 'PupilTracking':
            item = GroupPupilTracking(self)
        elif group_type == 'EyeTracking':
            item = GroupEyeTracking(self)
        elif group_type == 'CompassDirection':
            item = GroupCompassDirection(self)
        elif group_type == 'Position':
            item = GroupPosition(self)
        if group_type != '-- Add group --':
            if metadata is not None:
                item.write_fields(data=metadata)
            item.form_name.textChanged.connect(self.refresh_del_combo)
            self.groups_list.append(item)
            nWidgetsVbox = self.vbox1.count()
            self.vbox1.insertWidget(nWidgetsVbox-1, item)  # insert before the stretch
            self.combo1.setCurrentIndex(0)
            self.combo2.addItem(item.form_name.text())
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
            if v > 1 or k in ['Device', 'TimeSeries']:
                data[k] = []
        # iterate over existing groups and copy their metadata
        for grp in self.groups_list:
            if grp_type_count[grp.group_type] > 1 or grp.group_type in ['Device', 'TimeSeries']:
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
