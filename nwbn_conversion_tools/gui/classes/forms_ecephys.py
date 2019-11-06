from PySide2.QtWidgets import (QLineEdit, QVBoxLayout, QGridLayout, QLabel,
                             QGroupBox, QComboBox, QCheckBox, QMessageBox)
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from nwbn_conversion_tools.gui.classes.forms_misc import GroupDecompositionSeries
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from itertools import groupby


class GroupElectrodeGroup(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.ElectrodeGroup fields filling form."""
        super().__init__()
        self.setTitle('ElectrodeGroup')
        self.parent = parent
        self.group_type = 'ElectrodeGroup'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('ElectrodeGroup')
        self.lin_name.setToolTip("The unique name of this ElectrodeGroup.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupElectrodeGroup):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('ElectrodeGroup'+str(nInstances))

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_description = QLineEdit('description')
        self.lin_description.setToolTip("Description of this electrode group")

        self.lbl_location = QLabel('location<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_location = QLineEdit('location')
        self.lin_location.setToolTip("Location of this electrode group")

        self.lbl_device = QLabel('device<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_device = CustomComboBox()
        self.combo_device.setToolTip("The device that was used to record from this electrode group")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(4, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_location, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_location, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_device, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_device, 3, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_device.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupDevice):
                self.combo_device.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['description'] = self.lin_description.text()
        data['location'] = self.lin_location.text()
        data['device'] = self.combo_device.currentText()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_description.setText(data['description'])
        self.lin_location.setText(data['location'])
        self.combo_device.clear()
        self.combo_device.addItem(data['device'])


class GroupElectricalSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.ElectricalSeries fields filling form."""
        super().__init__()
        self.setTitle('ElectricalSeries')
        self.parent = parent
        self.group_type = 'ElectricalSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('ElectricalSeries')
        self.lin_name.setToolTip("The unique name of this ElectricalSeries dataset.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupElectricalSeries):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('ElectricalSeries'+str(nInstances))

        self.lbl_data = QLabel('data<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(True)
        self.chk_data.setToolTip(
            "The data this ElectricalSeries dataset stores.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_electrodes = QLabel('electrodes<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_electrodes = QCheckBox("Get from source file")
        self.chk_electrodes.setChecked(True)
        self.chk_electrodes.setToolTip(
            "The table region corresponding to the electrodes "
            "from which this series was recorded.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to convert to volts")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setToolTip(
            "The smallest meaningful difference (in specified unit) between values in data")

        self.lbl_timestamps = QLabel('timestamps:')
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
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
        self.lin_comments.setToolTip("Human-readable comments about this ElectricalSeries dataset")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this ElectricalSeries dataset")

        self.lbl_control = QLabel('control:')
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip(
            "Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_control_description = QLabel('control_description:')
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip(
            "Description of each control value.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(4, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_electrodes, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_electrodes, 2, 2, 1, 2)
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
        if self.chk_electrodes.isChecked():
            data['electrodes'] = True
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except ValueError as error:
            print(error)
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except ValueError as error:
            print(error)
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
        try:
            data['starting_time'] = float(self.lin_starting_time.text())
        except ValueError as error:
            print(error)
        try:
            data['rate'] = float(self.lin_rate.text())
        except ValueError as error:
            print(error)
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
        self.chk_data.setChecked(True)
        self.chk_electrodes.setChecked(True)
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


class GroupSpikeEventSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.SpikeEventSeries fields filling form."""
        super().__init__()
        self.setTitle('SpikeEventSeries')
        self.parent = parent
        self.group_type = 'SpikeEventSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('SpikeEventSeries')
        self.lin_name.setToolTip("The unique name of this SpikeEventSeries.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupSpikeEventSeries):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('SpikeEventSeries'+str(nInstances))

        self.lbl_data = QLabel('data<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(True)
        self.chk_data.setToolTip(
            "The data this SpikeEventSeries dataset stores.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_timestamps = QLabel('timestamps<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(True)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_electrodes = QLabel('electrodes<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_electrodes = QCheckBox("Get from source file")
        self.chk_electrodes.setChecked(True)
        self.chk_electrodes.setToolTip(
            "The table region corresponding to the electrodes from which this series was recorded.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to convert to volts")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
        self.lin_resolution.setToolTip(
            "The smallest meaningful difference (in specified unit) between values in data")

        self.lbl_comments = QLabel('comments:')
        self.lin_comments = QLineEdit('')
        self.lin_comments.setPlaceholderText("comments")
        self.lin_comments.setToolTip("Human-readable comments about this SpikeEventSeries dataset")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this SpikeEventSeries dataset")

        self.lbl_control = QLabel('control:')
        self.chk_control = QCheckBox("Get from source file")
        self.chk_control.setChecked(False)
        self.chk_control.setToolTip(
            "Numerical labels that apply to each element in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_control_description = QLabel('control_description:')
        self.chk_control_description = QCheckBox("Get from source file")
        self.chk_control_description.setChecked(False)
        self.chk_control_description.setToolTip(
            "Description of each control value.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(4, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_data, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_data, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_timestamps, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 2, 2, 1, 2)
        self.grid.addWidget(self.lbl_electrodes, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_electrodes, 3, 2, 1, 2)
        self.grid.addWidget(self.lbl_conversion, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 5, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 5, 2, 1, 4)
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
        if self.chk_electrodes.isChecked():
            data['electrodes'] = True
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except ValueError as error:
            print(error)
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except ValueError as error:
            print(error)
        if self.chk_timestamps.isChecked():
            data['timestamps'] = True
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
        self.chk_data.setChecked(True)
        self.chk_timestamps.setChecked(True)
        self.chk_electrodes.setChecked(True)
        if 'conversion' in data:
            self.lin_conversion.setText(str(data['conversion']))
        if 'resolution' in data:
            self.lin_resolution.setText(str(data['resolution']))
        if 'comments' in data:
            self.lin_comments.setText(data['comments'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)


class GroupEventDetection(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.EventDetection fields filling form."""
        super().__init__()
        self.setTitle('EventDetection')
        self.parent = parent
        self.group_type = 'EventDetection'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('EventDetection')
        self.lin_name.setToolTip("The unique name of this EventDetection")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupEventDetection):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('EventDetection'+str(nInstances))

        self.lbl_detection_method = QLabel('detection_method<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_detection_method = QLineEdit('detection_method')
        self.lin_detection_method.setToolTip(
            "Description of how events were detected, such as voltage threshold, "
            "or dV/dT threshold, as well as relevant values")

        self.lbl_source_electricalseries = QLabel('source_electricalseries<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_source_electricalseries = CustomComboBox()
        self.combo_source_electricalseries.setToolTip("The source electrophysiology data")

        self.lbl_source_idx = QLabel('source_idx<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_source_idx = QCheckBox("Get from source file")
        self.chk_source_idx.setChecked(True)
        self.chk_source_idx.setToolTip(
            "Indices (zero-based) into source ElectricalSeries "
            "data array corresponding to time of event. \nModule description should define "
            "what is meant by time of event (e.g., .25msec before action potential peak, \n"
            "zero-crossing time, etc). The index points to each event from the raw data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_times = QLabel('times<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_times = QCheckBox("Get from source file")
        self.chk_times.setChecked(True)
        self.chk_times.setToolTip(
            "Timestamps of events, in Seconds.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_detection_method, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_detection_method, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_source_electricalseries, 2, 0, 1, 2)
        self.grid.addWidget(self.combo_source_electricalseries, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_source_idx, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_source_idx, 3, 2, 1, 2)
        self.grid.addWidget(self.lbl_times, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_times, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_source_electricalseries.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupElectricalSeries):
                self.combo_source_electricalseries.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['detection_method'] = self.lin_detection_method.text()
        data['source_electricalseries'] = self.combo_source_electricalseries.currentText()
        if self.chk_source_idx.isChecked():
            data['source_idx'] = True
        if self.chk_times.isChecked():
            data['times'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_detection_method.setText(data['detection_method'])
        self.combo_source_electricalseries.clear()
        self.combo_source_electricalseries.addItem(data['source_electricalseries'])
        self.chk_source_idx.setChecked(True)
        self.chk_times.setChecked(True)


class GroupEventWaveform(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.EventWaveform fields filling form."""
        super().__init__()
        self.setTitle('EventWaveform')
        self.parent = parent
        self.group_type = 'EventWaveform'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('EventWaveform')
        self.lin_name.setToolTip("The unique name of this EventWaveform")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupEventWaveform):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('EventWaveform'+str(nInstances))

        self.lbl_spike_event_series = QLabel('spike_event_series<span style="color:'+required_asterisk_color+';">*</span>:')
        self.combo_spike_event_series = CustomComboBox()
        self.combo_spike_event_series.setToolTip("SpikeEventSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_spike_event_series, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_spike_event_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_spike_event_series.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupSpikeEventSeries):
                self.combo_spike_event_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['spike_event_series'] = self.combo_spike_event_series.currentText()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.combo_spike_event_series.clear()
        self.combo_spike_event_series.addItem(data['spike_event_series'])


class GroupLFP(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.LFP fields filling form."""
        super().__init__()
        self.setTitle('LFP')
        self.parent = parent
        self.group_type = 'LFP'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('LFP')
        self.lin_name.setToolTip("The unique name of this LFP")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupLFP):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('LFP'+str(nInstances))

        self.lbl_electrical_series = QLabel('electrical_series<span style="color:'+required_asterisk_color+';">*</span>:')
        self.electrical_series = GroupElectricalSeries(self)
        #self.combo_electrical_series = CustomComboBox()
        #self.combo_electrical_series.setToolTip("ElectricalSeries to store in this interface")

        self.lbl_decomposition_series = QLabel('decomposition_series<span style="color:'+required_asterisk_color+';">*</span>:')
        self.decomposition_series = GroupDecompositionSeries(self)
        #self.combo_decomposition_series = CustomComboBox()
        #self.combo_decomposition_series.setToolTip("DecompositionSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_electrical_series, 1, 0, 1, 2)
        self.grid.addWidget(self.electrical_series, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_decomposition_series, 2, 0, 1, 2)
        self.grid.addWidget(self.decomposition_series, 2, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass
        # self.combo_electrical_series.clear()
        # self.combo_decomposition_series.clear()
        # for grp in self.parent.groups_list:
        #     if isinstance(grp, GroupElectricalSeries):
        #         self.combo_electrical_series.addItem(grp.lin_name.text())
        #     if isinstance(grp, GroupDecompositionSeries):
        #         self.combo_decomposition_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['electrical_series'] = self.electrical_series.read_fields()
        data['decomposition_series'] = self.decomposition_series.read_fields()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        # self.combo_electrical_series.clear()
        # self.combo_electrical_series.addItem(data['electrical_series'])
        # self.combo_decomposition_series.clear()
        # self.combo_decomposition_series.addItem(data['decomposition_series'])


class GroupFilteredEphys(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.FilteredEphys fields filling form."""
        super().__init__()
        self.setTitle('FilteredEphys')
        self.parent = parent
        self.group_type = 'FilteredEphys'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('FilteredEphys')
        self.lin_name.setToolTip("The unique name of this FilteredEphys")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupFilteredEphys):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('FilteredEphys'+str(nInstances))

        self.lbl_electrical_series = QLabel('electrical_series<span style="color:'+required_asterisk_color+';">*</span>:')
        self.electrical_series = GroupElectricalSeries(self)
        # self.combo_electrical_series = CustomComboBox()
        # self.combo_electrical_series.setToolTip("ElectricalSeries to store in this interface")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_electrical_series, 1, 0, 1, 2)
        self.grid.addWidget(self.electrical_series, 1, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass
        # self.combo_electrical_series.clear()
        # for grp in self.parent.groups_list:
        #     if isinstance(grp, GroupElectricalSeries):
        #         self.combo_electrical_series.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['electrical_series'] = self.electrical_series.read_fields()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        # self.combo_electrical_series.clear()
        # self.combo_electrical_series.addItem(data['electrical_series'])


class GroupFeatureExtraction(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.ecephys.FeatureExtraction fields filling form."""
        super().__init__()
        self.setTitle('FeatureExtraction')
        self.parent = parent
        self.group_type = 'FeatureExtraction'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('FeatureExtraction')
        self.lin_name.setToolTip("The unique name of this FeatureExtraction")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupFeatureExtraction):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('FeatureExtraction'+str(nInstances))

        self.lbl_electrodes = QLabel('electrodes<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_electrodes = QCheckBox("Get from source file")
        self.chk_electrodes.setChecked(True)
        self.chk_electrodes.setToolTip(
            "The table region corresponding to the electrodes from which this series was recorded.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_description = QLineEdit('')
        self.lin_description.setToolTip("A description for each feature extracted")

        self.lbl_times = QLabel('times<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_times = QCheckBox("Get from source file")
        self.chk_times.setChecked(True)
        self.chk_times.setToolTip(
            "The times of events that features correspond to.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_features = QLabel('features<span style="color:'+required_asterisk_color+';">*</span>:')
        self.chk_features = QCheckBox("Get from source file")
        self.chk_features.setChecked(True)
        self.chk_features.setToolTip(
            "Features for each channel.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_electrodes, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_electrodes, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_times, 3, 0, 1, 2)
        self.grid.addWidget(self.chk_times, 3, 2, 1, 2)
        self.grid.addWidget(self.lbl_features, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_features, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        if self.chk_electrodes.isChecked():
            data['electrodes'] = True
        data['description'] = self.lin_description.text()
        if self.chk_times.isChecked():
            data['times'] = True
        if self.chk_features.isChecked():
            data['features'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.chk_electrodes.setChecked(True)
        self.lin_description.setText(data['description'])
        self.chk_times.setChecked(True)
        self.chk_features.setChecked(True)


class GroupEcephys(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Ecephys module fields filling form."""
        super().__init__()
        self.setTitle('Ecephys')
        self.group_type = 'Ecephys'
        self.groups_list = []

        self.combo1 = CustomComboBox()
        self.combo1.addItem('-- Add group --')
        self.combo1.addItem('Device')
        self.combo1.addItem('ElectrodeGroup')
        self.combo1.addItem('ElectricalSeries')
        self.combo1.addItem('SpikeEventSeries')
        self.combo1.addItem('EventDetection')
        self.combo1.addItem('EventWaveform')
        self.combo1.addItem('LFP')
        self.combo1.addItem('FilteredEphys')
        self.combo1.addItem('FeatureExtraction')
        self.combo1.addItem('DecompositionSeries')
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

    def add_group(self, group_type, write_data=None):
        """Adds group form."""
        if group_type == 'combo':
            group_type = str(self.combo1.currentText())
        if group_type == 'Device':
            item = GroupDevice(self)
        elif group_type == 'ElectrodeGroup':
            item = GroupElectrodeGroup(self)
        elif group_type == 'ElectricalSeries':
            item = GroupElectricalSeries(self)
        elif group_type == 'SpikeEventSeries':
            item = GroupSpikeEventSeries(self)
        elif group_type == 'EventDetection':
            item = GroupEventDetection(self)
        elif group_type == 'EventWaveform':
            item = GroupEventWaveform(self)
        elif group_type == 'LFP':
            item = GroupLFP(self)
        elif group_type == 'FilteredEphys':
            item = GroupFilteredEphys(self)
        elif group_type == 'FeatureExtraction':
            item = GroupFeatureExtraction(self)
        elif group_type == 'DecompositionSeries':
            item = GroupDecompositionSeries(self)
        if group_type != '-- Add group --':
            if write_data is not None:
                item.write_fields(data=write_data)
            item.lin_name.textChanged.connect(self.refresh_del_combo)
            self.groups_list.append(item)
            nWidgetsVbox = self.vbox1.count()
            self.vbox1.insertWidget(nWidgetsVbox-1, item)  # insert before the stretch
            self.combo1.setCurrentIndex(0)
            self.combo2.addItem(item.lin_name.text())
            self.refresh_children()

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
                        if hasattr(self.vbox1.itemAt(i).widget(), 'lin_name'):
                            if self.vbox1.itemAt(i).widget().lin_name.text() == group_name:
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
        error = None
        data = {}
        # group_type counts, if there are multiple groups of same type, they are saved in a list
        grp_types = [grp.group_type for grp in self.groups_list]
        grp_type_count = {value: len(list(freq)) for value, freq in groupby(sorted(grp_types))}
        # initiate lists as values for groups keys with count > 1
        for k, v in grp_type_count.items():
            if v > 1:
                data[k] = []
        # iterate over existing groups and copy their metadata
        for grp in self.groups_list:
            if grp_type_count[grp.group_type] > 1:
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
