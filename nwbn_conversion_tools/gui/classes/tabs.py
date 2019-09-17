from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QApplication, QAction, QGroupBox,
    QTabWidget, QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QLabel, QFileDialog, QComboBox, QScrollArea)
from nwbn_conversion_tools.gui.classes.forms import (GroupNwbfile, GroupGeneral,
    GroupOphys, GroupEphys, GroupSubject, GroupDevice)
import yaml
import numpy as np

class TabMetafile(QWidget):
    def __init__(self, parent):
        """Tab for Meta-data file editing."""
        super().__init__()
        self.groups_list = []

        # Left-side panel: forms
        btn_close_tab = QPushButton('Close tab')
        btn_close_tab.clicked.connect(lambda: self.close_tab())
        btn_load_meta = QPushButton('Load from file')
        btn_load_meta.clicked.connect(lambda: self.open_meta_file())
        btn_save_meta = QPushButton('Save to file')
        btn_save_meta.clicked.connect(lambda: self.save_meta_file())
        btn_form_editor = QPushButton('Form -> Editor')
        btn_form_editor.clicked.connect(lambda: self.form_to_editor())
        self.l_combo1 = CustomComboBox()
        self.l_combo1.addItem('-- Add group --')
        self.l_combo1.addItem('Subject')
        self.l_combo1.addItem('Device')
        self.l_combo1.addItem('Ophys')
        self.l_combo1.addItem('Ephys')
        self.l_combo1.activated.connect(self.add_group)
        self.l_combo2 = CustomComboBox()
        self.l_combo2.addItem('-- Del group --')
        self.l_combo2.activated.connect(self.del_group)

        l_grid1 = QGridLayout()
        l_grid1.setColumnStretch(6, 1)
        l_grid1.addWidget(btn_close_tab, 0, 0, 1, 2)
        l_grid1.addWidget(btn_load_meta, 0, 2, 1, 2)
        l_grid1.addWidget(btn_save_meta, 0, 4, 1, 2)
        l_grid1.addWidget(QLabel(), 0, 6, 1, 4)
        l_grid1.addWidget(btn_form_editor, 0, 10, 1, 2)
        l_grid1.addWidget(self.l_combo1, 1, 0, 1, 3)
        l_grid1.addWidget(self.l_combo2, 1, 3, 1, 3)

        self.box_general = GroupGeneral(self)
        self.groups_list.append(self.box_general)
        self.box_nwbfile = GroupNwbfile(self)
        self.groups_list.append(self.box_nwbfile)

        self.l_vbox1 = QVBoxLayout()
        self.l_vbox1.addWidget(self.box_general)
        self.l_vbox1.addWidget(self.box_nwbfile)
        self.l_vbox1.addStretch()
        scroll_aux = QWidget()
        scroll_aux.setLayout(self.l_vbox1)
        l_scroll = QScrollArea()
        l_scroll.setWidget(scroll_aux)
        l_scroll.setWidgetResizable(True)

        self.l_vbox2 = QVBoxLayout()
        self.l_vbox2.addLayout(l_grid1)
        self.l_vbox2.addWidget(QLabel())
        self.l_vbox2.addWidget(l_scroll)

        # Right-side panel: meta-data text
        btn_editor_form = QPushButton('Form <- Editor')
        btn_editor_form.clicked.connect(lambda: self.editor_to_form())
        r_grid1 = QGridLayout()
        r_grid1.setColumnStretch(1, 1)
        r_grid1.addWidget(btn_editor_form, 0, 0, 1, 1)
        r_grid1.addWidget(QLabel(), 0, 1, 1, 1)

        self.editor = QTextEdit()
        r_vbox1 = QVBoxLayout()
        r_vbox1.addLayout(r_grid1)
        r_vbox1.addWidget(self.editor)

        # Main Layout
        left_w = QWidget()
        left_w.setLayout(self.l_vbox2)
        right_w = QWidget()
        right_w.setLayout(r_vbox1)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(left_w)
        self.splitter.addWidget(right_w)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)

        # Background color
        p = self.palette()
        p.setColor(self.backgroundRole(), QtCore.Qt.white)
        self.setPalette(p)


    def close_tab(self):
        """Closes current tab."""
        pass


    def add_group(self):
        """Adds group form."""
        group_name = str(self.l_combo1.currentText())
        nWidgetsVbox = self.l_vbox1.count()
        if group_name == 'Subject':
            self.box_subject = GroupSubject(self)
            self.groups_list.append(self.box_subject)
            self.l_vbox1.insertWidget(nWidgetsVbox-1, self.box_subject) #insert before the stretch
        if group_name == 'Device':
            self.box_device = GroupDevice(self)
            self.groups_list.append(self.box_device)
            self.l_vbox1.insertWidget(nWidgetsVbox-1, self.box_device) #insert before the stretch
        if group_name == 'Ophys':
            self.box_ophys = GroupOphys(self)
            self.groups_list.append(self.box_ophys)
            self.l_vbox1.insertWidget(nWidgetsVbox-1, self.box_ophys) #insert before the stretch
        if group_name == 'Ephys':
            self.box_ephys = GroupEphys(self)
            self.groups_list.append(self.box_ephys)
            self.l_vbox1.insertWidget(nWidgetsVbox-1, self.box_ephys) #insert before the stretch
        if group_name != '-- Add group --':
            self.l_combo1.removeItem(self.l_combo1.findText(group_name))
            self.l_combo1.setCurrentIndex(0)
            self.l_combo2.addItem(group_name)


    def del_group(self):
        """Deletes group form."""
        group_name = str(self.l_combo2.currentText())
        nWidgetsVbox = self.l_vbox1.count()
        if group_name == 'Subject':
            ind = np.where([isinstance(self.l_vbox1.itemAt(i).widget(), GroupSubject)
                            for i in range(nWidgetsVbox)])[0][0]
            self.l_vbox1.itemAt(ind).widget().setParent(None) #deletes widget
            self.groups_list.remove(self.box_subject)           #deletes list item
            del self.box_subject                                #deletes attribute
        if group_name == 'Device':
            ind = np.where([isinstance(self.l_vbox1.itemAt(i).widget(), GroupDevice)
                            for i in range(nWidgetsVbox)])[0][0]
            self.l_vbox1.itemAt(ind).widget().setParent(None) #deletes widget
            self.groups_list.remove(self.box_device)           #deletes list item
            del self.box_device                                #deletes attribute
        if group_name == 'Ophys':
            ind = np.where([isinstance(self.l_vbox1.itemAt(i).widget(), GroupOphys)
                            for i in range(nWidgetsVbox)])[0][0]
            self.l_vbox1.itemAt(ind).widget().setParent(None) #deletes widget
            self.groups_list.remove(self.box_ophys)           #deletes list item
            del self.box_ophys                                #deletes attribute
        if group_name == 'Ephys':
            ind = np.where([isinstance(self.l_vbox1.itemAt(i).widget(), GroupEphys)
                            for i in range(nWidgetsVbox)])[0][0]
            self.l_vbox1.itemAt(ind).widget().setParent(None) #deletes widget
            self.groups_list.remove(self.box_ephys)           #deletes list item
            del self.box_ephys                                #deletes attribute
        if group_name != '-- Del group --':
            self.l_combo2.removeItem(self.l_combo2.findText(group_name))
            self.l_combo2.setCurrentIndex(0)
            self.l_combo1.addItem(group_name)


    def open_meta_file(self):
        ''' Opens .yml file containing metadata for NWB.'''
        filename, ftype = QFileDialog.getOpenFileName(self, 'Open file', '', "(*.yml)")
        if ftype=='(*.yml)':
            with open(filename) as f:
                data = yaml.safe_load(f)
            txt = yaml.dump(data, default_flow_style=False)
            self.editor.setText(txt)


    def save_meta_file(self):
        ''' Saves metadata to .yml file.'''
        filename, _ = QFileDialog.getSaveFileName(self, 'Save file', '', "(*.yml)")
        if filename:
            data = {}
            for grp in self.groups_list:
                data[grp.group_name] = grp.read_fields()
            with open(filename, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)


    def form_to_editor(self):
        """Loads data from form to editor."""
        data = {}
        for grp in self.groups_list:
            data[grp.group_name] = grp.read_fields()
        txt = yaml.dump(data, default_flow_style=False)
        self.editor.setText(txt)


    def editor_to_form(self):
        """Loads data from editor to form."""
        pass




class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
