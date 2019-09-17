from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QComboBox,
    QCheckBox)
from datetime import datetime
import numpy as np
import yaml
import os



class GroupIntervalSeries(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.misc.IntervalSeries fields filling form."""
        super().__init__()
        self.setTitle('IntervalSeries')
        self.parent = parent
        self.group_name = 'IntervalSeries'

        self.lbl_name = QLabel('name:')
        self.lin_name = QLineEdit('IntervalSeries')
        self.lin_name.setToolTip("The unique name of this IntervalSeries dataset")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupIntervalSeries):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('IntervalSeries'+str(nInstances))

        self.lbl_data = QLabel('data:')
        self.chk_data = QCheckBox("Get from source file")
        self.chk_data.setChecked(False)
        self.chk_data.setToolTip(">0 if interval started, <0 if interval ended.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.lbl_timestamps = QLabel('timestamps:')
        self.chk_timestamps = QCheckBox("Get from source file")
        self.chk_timestamps.setChecked(False)
        self.chk_timestamps.setToolTip("Timestamps for samples stored in data.\n"
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
        if self.chk_data.isChecked():
            data['data'] = True
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
        if 'data' in data:
            self.chk_data.setChecked(True)
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




class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
