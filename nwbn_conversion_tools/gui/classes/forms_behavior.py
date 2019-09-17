from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox, QComboBox,
    QCheckBox, QFileDialog, QStyle)
from nwbn_conversion_tools.gui.classes.forms_general import GroupDevice
from datetime import datetime
import numpy as np
import yaml
import os



class GroupBehavior(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Ophys module fields filling form."""
        super().__init__()
        self.setTitle('Ophys')
        self.group_name = 'Ophys'
        self.groups_list = []

        self.combo1 = CustomComboBox()
        self.combo1.addItem('-- Add group --')
        self.combo1.addItem('Device')
        self.combo1.addItem('OpticalChannel')
        self.combo1.addItem('ImagingPlane')
        self.combo1.addItem('TwoPhotonSeries')
        self.combo1.addItem('CorrectedImageStack')
        self.combo1.addItem('MotionCorrection')
        self.combo1.addItem('PlaneSegmentation')
        self.combo1.addItem('ImageSegmentation')
        self.combo1.addItem('RoiResponseSeries')
        self.combo1.addItem('DfOverF')
        self.combo1.addItem('Fluorescence')
        self.combo1.addItem('GrayscaleVolume')
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
        elif group_type == 'OpticalChannel':
            item = GroupOpticalChannel(self)
        elif group_type == 'ImagingPlane':
            item = GroupImagingPlane(self)
        elif group_type == 'TwoPhotonSeries':
            item = GroupTwoPhotonSeries(self)
        elif group_type == 'CorrectedImageStack':
            item = GroupCorrectedImageStack(self)
        elif group_type == 'MotionCorrection':
            item = GroupMotionCorrection(self)
        elif group_type == 'PlaneSegmentation':
            item = GroupPlaneSegmentation(self)
        elif group_type == 'ImageSegmentation':
            item = GroupImageSegmentation(self)
        elif group_type == 'RoiResponseSeries':
            item = GroupRoiResponseSeries(self)
        elif group_type == 'DfOverF':
            item = GroupDfOverF(self)
        elif group_type == 'Fluorescence':
            item = GroupFluorescence(self)
        elif group_type == 'GrayscaleVolume':
            item = GroupGrayscaleVolume(self)
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
