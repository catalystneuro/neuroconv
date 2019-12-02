from PySide2.QtWidgets import (QLineEdit, QGridLayout, QLabel, QGroupBox,
                             QComboBox, QCheckBox)
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.forms_base import GroupTimeSeries


class GroupIntervalSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.misc.IntervalSeries fields filling form."""
        super().__init__()
        self.setTitle('IntervalSeries')
        self.parent = parent
        self.group_type = 'IntervalSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('IntervalSeries')
        self.lin_name.setToolTip("The unique name of this IntervalSeries dataset")

        self.lbl_timestamps = QLabel('timestamps:')
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip(
            "Timestamps for samples stored in data.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_comments = QLabel('comments:')
        self.lin_comments = QLineEdit('')
        self.lin_comments.setPlaceholderText("comments")
        self.lin_comments.setToolTip("Human-readable comments about this IntervalSeries dataset")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this IntervalSeries dataset")

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
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 2, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 2, 2, 1, 2)
        self.grid.addWidget(self.lbl_comments, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_comments, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 6, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 6, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
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
        if 'timestamps' in data:
            self.chk_timestamps.setChecked(True)
        if 'comments' in data:
            self.lin_comments.setText(data['comments'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)


class GroupUnits(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.misc.Units fields filling form."""
        super().__init__()
        self.setTitle('Units')
        self.parent = parent
        self.group_type = 'Units'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('Units')
        self.lin_name.setToolTip("The unique name of this Units interface")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupUnits):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('Units'+str(nInstances))

        self.lbl_id = QLabel('id:')
        self.chk_id = QCheckBox("Get from source file")
        self.chk_id.setChecked(False)
        self.chk_id.setToolTip(
            "The identifiers for the units stored in this interface.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip("A description of what is in this table")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_id, 1, 0, 1, 2)
        self.grid.addWidget(self.chk_id, 1, 2, 1, 2)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 2, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['description'] = self.lin_description.text()
        if self.chk_id.isChecked():
            data['id'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'id' in data:
            self.chk_id.setChecked(True)


class GroupDecompositionSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.misc.DecompositionSeries fields filling form."""
        super().__init__()
        self.setTitle('DecompositionSeries')
        self.parent = parent
        self.group_type = 'DecompositionSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('DecompositionSeries')
        self.lin_name.setToolTip("The unique name of this DecompositionSeries dataset")

        self.lbl_description = QLabel('description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_description = QLineEdit('description')
        self.lin_description.setToolTip("Description of this DecompositionSeries")

        self.lbl_metric = QLabel('metric<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_metric = QLineEdit('amplitude')
        self.lin_metric.setToolTip("Metric of analysis. Recommended: ‘phase’, ‘amplitude’, ‘power’")

        self.lbl_unit = QLabel('unit:')
        self.lin_unit = QLineEdit('')
        self.lin_unit.setPlaceholderText("no unit")
        self.lin_unit.setToolTip("SI unit of measurement")

        self.lbl_bands = QLabel('bands:')
        self.chk_bands = QCheckBox("Get from source file")
        self.chk_bands.setChecked(False)
        self.chk_bands.setToolTip(
            "A table for describing the frequency bands that the signal was decomposed into.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_source_timeseries = QLabel('source_timeseries:')
        self.combo_source_timeseries = CustomComboBox()
        self.combo_source_timeseries.setToolTip("The input TimeSeries from this analysis")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip("Scalar to multiply each element by to convert to unit")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
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
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_metric, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_metric, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_unit, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_unit, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_bands, 5, 0, 1, 2)
        self.grid.addWidget(self.chk_bands, 5, 2, 1, 2)
        self.grid.addWidget(self.lbl_source_timeseries, 6, 0, 1, 2)
        self.grid.addWidget(self.combo_source_timeseries, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_conversion, 7, 0, 1, 2)
        self.grid.addWidget(self.lin_conversion, 7, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 8, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 8, 2, 1, 4)
        self.grid.addWidget(self.lbl_timestamps, 9, 0, 1, 2)
        self.grid.addWidget(self.chk_timestamps, 9, 2, 1, 2)
        self.grid.addWidget(self.lbl_starting_time, 10, 0, 1, 2)
        self.grid.addWidget(self.lin_starting_time, 10, 2, 1, 4)
        self.grid.addWidget(self.lbl_rate, 11, 0, 1, 2)
        self.grid.addWidget(self.lin_rate, 11, 2, 1, 4)
        self.grid.addWidget(self.lbl_comments, 12, 0, 1, 2)
        self.grid.addWidget(self.lin_comments, 12, 2, 1, 4)
        self.grid.addWidget(self.lbl_control, 13, 0, 1, 2)
        self.grid.addWidget(self.chk_control, 13, 2, 1, 2)
        self.grid.addWidget(self.lbl_control_description, 14, 0, 1, 2)
        self.grid.addWidget(self.chk_control_description, 14, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_source_timeseries.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupTimeSeries):
                self.combo_source_timeseries.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['description'] = self.lin_description.text()
        data['metric'] = self.lin_metric.text()
        data['unit'] = self.lin_unit.text()
        if self.chk_bands.isChecked():
            data['bands'] = True
        data['source_timeseries'] = self.combo_source_timeseries.currentText()
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
        if self.chk_control.isChecked():
            data['control'] = True
        if self.chk_control_description.isChecked():
            data['control_description'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_description.setText(data['description'])
        self.lin_metric.setText(data['metric'])
        if 'unit' in data:
            self.lin_unit.setText(str(data['unit']))
        if 'bands' in data:
            self.chk_bands.setChecked(True)
        self.combo_source_timeseries.clear()
        self.combo_source_timeseries.addItem(data['source_timeseries'])
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
        if 'control' in data:
            self.chk_control.setChecked(True)
        if 'control_description' in data:
            self.chk_control_description.setChecked(True)


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
