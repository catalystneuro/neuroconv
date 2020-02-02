from PySide2.QtWidgets import (QLineEdit, QGridLayout, QLabel, QGroupBox,
                             QComboBox, QCheckBox)
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from nwbn_conversion_tools.gui.classes.collapsible_box import CollapsibleBox


class GroupTimeSeries(QGroupBox):
#class GroupTimeSeries(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.base.TimeSeries fields filling form."""
        super().__init__()#title='TimeSeries', parent=parent)
        self.setTitle('TimeSeries')
        self.parent = parent
        self.group_type = 'TimeSeries'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('TimeSeries')
        self.lin_name.setToolTip("The unique name of this TimeSeries dataset")

        self.lbl_unit = QLabel('unit:')
        self.lin_unit = QLineEdit('')
        self.lin_unit.setPlaceholderText("unit")
        self.lin_unit.setToolTip("The base unit of measurement (should be SI unit)")

        self.lbl_conversion = QLabel('conversion:')
        self.lin_conversion = QLineEdit('')
        self.lin_conversion.setPlaceholderText("1.0")
        self.lin_conversion.setToolTip(
            "Scalar to multiply each element in data "
            "to convert it to the specified unit")

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
        self.lin_resolution.setToolTip(
            "The smallest meaningful difference (in "
            "specified unit) between values in data")

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
        self.lin_comments.setToolTip("Human-readable comments about this TimeSeries dataset")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this TimeSeries dataset")

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
        self.grid.addWidget(self.lbl_unit, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_unit, 2, 2, 1, 4)
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

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        try:
            data['conversion'] = float(self.lin_conversion.text())
        except ValueError:
            pass
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

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(metadata['name'])
        if 'unit' in metadata:
            self.lin_unit.setText(metadata['unit'])
        if 'conversion' in metadata:
            self.lin_conversion.setText(str(metadata['conversion']))
        if 'resolution' in metadata:
            self.lin_resolution.setText(str(metadata['resolution']))
        if 'timestamps' in metadata:
            self.chk_timestamps.setChecked(True)
        if 'starting_time' in metadata:
            self.lin_starting_time.setText(str(metadata['starting_time']))
        if 'rate' in metadata:
            self.lin_rate.setText(str(metadata['rate']))
        if 'comments' in metadata:
            self.lin_comments.setText(metadata['comments'])
        if 'description' in metadata:
            self.lin_description.setText(metadata['description'])
        #self.setContentLayout(self.grid)


class GroupImage(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.base.Image fields filling form."""
        super().__init__()
        self.setTitle('Image')
        self.parent = parent
        self.group_type = 'Image'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('Image')
        self.lin_name.setToolTip("The unique name of this Image dataset")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupImage):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('Image'+str(nInstances))

        self.lbl_resolution = QLabel('resolution:')
        self.lin_resolution = QLineEdit('')
        self.lin_resolution.setPlaceholderText("1.0")
        self.lin_resolution.setToolTip("Pixels / cm")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip(" Description of this Image dataset")

        self.lbl_help = QLabel('help:')
        self.lin_help = QLineEdit('')
        self.lin_help.setPlaceholderText("help")
        self.lin_help.setToolTip("Helpful hint for user")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_resolution, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_resolution, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_help, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_help, 4, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        try:
            data['resolution'] = float(self.lin_resolution.text())
        except ValueError as error:
            print(error)
        data['description'] = self.lin_description.text()
        data['help'] = self.lin_help.text()
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(metadata['name'])
        if 'resolution' in metadata:
            self.lin_resolution.setText(str(metadata['resolution']))
        if 'description' in metadata:
            self.lin_description.setText(metadata['description'])
        if 'help' in metadata:
            self.lin_help.setText(metadata['help'])


class GroupImages(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.base.Images fields filling form."""
        super().__init__()
        self.setTitle('Images')
        self.parent = parent
        self.group_type = 'Images'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('Images')
        self.lin_name.setToolTip("The name of this set of images")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupImages):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('Images'+str(nInstances))

        self.lbl_images = QLabel('images:')
        self.combo_images = CustomComboBox()
        self.combo_images.setToolTip("Image objects")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip("Description of images")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_images, 1, 0, 1, 2)
        self.grid.addWidget(self.combo_images, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 2, 2, 1, 4)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_images.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupImage):
                self.combo_images.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['images'] = self.combo_images.currentText()
        data['description'] = self.lin_description.text()
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(metadata['name'])
        self.combo_images.clear()
        self.combo_images.addItem(metadata['images'])
        if 'description' in metadata:
            self.lin_description.setText(metadata['description'])


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
