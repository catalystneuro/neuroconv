from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
    QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QLabel, QFileDialog, QGroupBox, QMessageBox, QComboBox, QScrollArea)
from nwbn_conversion_tools.gui.classes.forms import (GroupFiles, GroupNwbfile,
    GroupOphys, GroupEphys, GroupSubject, GroupDevice)
import numpy as np
import yaml
import os
import sys


class Application(QMainWindow):
    def __init__(self, modules=['files','nwbfile']):
        super().__init__()

        self.centralwidget = QWidget()
        self.setCentralWidget(self.centralwidget)
        self.resize(1200, 900)
        self.setWindowTitle('NWB conversion tool')

        #Initialize GUI elements
        self.init_gui(modules=modules)
        self.show()


    def init_gui(self, modules):
        """Initiates GUI elements."""
        mainMenu = self.menuBar()

        helpMenu = mainMenu.addMenu('Help')
        action_about = QAction('About', self)
        helpMenu.addAction(action_about)
        action_about.triggered.connect(self.about)

        # Center panels -------------------------------------------------------
        self.groups_list = []

        # Left-side panel: forms
        btn_save_meta = QPushButton('Save metafile')
        btn_save_meta.clicked.connect(lambda: self.save_meta_file())
        btn_run_conversion = QPushButton('Run conversion')
        btn_run_conversion.clicked.connect(lambda: self.run_conversion())
        btn_form_editor = QPushButton('Form -> Editor')
        btn_form_editor.clicked.connect(lambda: self.form_to_editor())

        l_grid1 = QGridLayout()
        l_grid1.setColumnStretch(2, 1)
        l_grid1.addWidget(btn_save_meta, 0, 0, 1, 1)
        l_grid1.addWidget(btn_run_conversion, 0, 1, 1, 1)
        l_grid1.addWidget(QLabel(), 0, 2, 1, 1)
        l_grid1.addWidget(btn_form_editor, 0, 3, 1, 1)

        self.l_vbox1 = QVBoxLayout()
        self.box_files = GroupFiles(self)
        self.groups_list.append(self.box_files)
        self.l_vbox1.addWidget(self.box_files)
        self.box_nwbfile = GroupNwbfile(self)
        self.groups_list.append(self.box_nwbfile)
        self.l_vbox1.addWidget(self.box_nwbfile)
        if 'ophys' in modules:
            self.box_ophys = GroupOphys(self)
            self.groups_list.append(self.box_ophys)
            self.l_vbox1.addWidget(self.box_ophys)
        if 'ephys' in modules:
            self.box_ephys = GroupEphys(self)
            self.groups_list.append(self.box_ephys)
            self.l_vbox1.addWidget(self.box_ephys)
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
        editor_label = QLabel('Metafile preview:')
        r_grid1 = QGridLayout()
        r_grid1.setColumnStretch(1, 1)
        r_grid1.addWidget(editor_label, 0, 0, 1, 1)
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
        self.centralwidget.setLayout(main_layout)

        # Background color
        p = self.palette()
        p.setColor(self.backgroundRole(), QtCore.Qt.white)
        self.setPalette(p)


    def save_meta_file(self):
        """Saves metadata to .yml file."""
        filename, _ = QFileDialog.getSaveFileName(self, 'Save file', '', "(*.yml)")
        if filename:
            data = {}
            for grp in self.groups_list:
                data[grp.group_name] = grp.read_fields()
            with open(filename, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)


    def run_conversion(self):
        """Runs conversion script."""
        pass


    def form_to_editor(self):
        """Loads data from form to editor."""
        data = {}
        for grp in self.groups_list:
            data[grp.group_name] = grp.read_fields()
        txt = yaml.dump(data, default_flow_style=False)
        self.editor.setText(txt)


    def about(self):
        """About dialog."""
        msg = QMessageBox()
        msg.setWindowTitle("About NWB conversion")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Version: 1.0.0 \n"+
                    "Shared tools for converting data from various formats to NWB:N 2.0.\n ")
        msg.setInformativeText("<a href='https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools'>NWB conversion tools Github page</a>")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()


    def closeEvent(self, event):
        """Before exiting, executes these actions."""
        event.accept()



class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)  #instantiate a QtGui (holder for the app)
    #if len(sys.argv)==1:
    #    fname = None
    #else:
    #    fname = sys.argv[1]
    ex = Application(modules=['files','nwbfile', 'ophys'])
    sys.exit(app.exec_())


def main(modules=['files','nwbfile']):  # If it was imported as a module
    """Sets up QT application."""
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)  #instantiate a QtGui (holder for the app)
    ex = Application(modules=['files','nwbfile'])
    sys.exit(app.exec_())
