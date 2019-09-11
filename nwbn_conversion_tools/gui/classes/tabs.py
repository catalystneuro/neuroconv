from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QApplication, QAction, QGroupBox,
    QTabWidget, QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QLabel, QFileDialog)
from nwbn_conversion_tools.gui.classes.forms import GroupNwbfile, GroupGeneral
import yaml

class TabMetafile(QWidget):
    def __init__(self, parent):
        """Tab for Meta-data file editing."""
        super().__init__()

        # Left-side panel: forms
        btn_load_meta = QPushButton('Load from file')
        btn_load_meta.clicked.connect(lambda: self.open_meta_file())
        btn_save_meta = QPushButton('Save to file')
        btn_save_meta.clicked.connect(lambda: self.save_meta_file())

        l_grid1 = QGridLayout()
        l_grid1.setColumnStretch(5, 1)
        l_grid1.addWidget(btn_load_meta, 0, 0, 1, 2)
        l_grid1.addWidget(btn_save_meta, 0, 2, 1, 2)
        l_grid1.addWidget(QLabel(), 0, 4, 1, 2)

        self.box_general = GroupGeneral(self)
        self.box_nwbfile = GroupNwbfile(self)

        l_vbox1 = QVBoxLayout()
        l_vbox1.addLayout(l_grid1)
        l_vbox1.addWidget(QLabel())
        l_vbox1.addWidget(self.box_general)
        l_vbox1.addWidget(self.box_nwbfile)
        l_vbox1.addStretch()

        # Right-side panel: meta-data text
        r_label1 = QLabel('Resulting meta-data file:')
        btn_editor_form = QPushButton('Editor -> Form')
        btn_editor_form.clicked.connect(lambda: self.editor_to_form())
        btn_form_editor = QPushButton('Form -> Editor')
        btn_form_editor.clicked.connect(lambda: self.form_to_editor())
        r_grid1 = QGridLayout()
        r_grid1.addWidget(r_label1, 0, 0, 1, 4)
        r_grid1.addWidget(btn_editor_form, 0, 4, 1, 1)
        r_grid1.addWidget(btn_form_editor, 0, 5, 1, 1)

        self.editor = QTextEdit()
        r_vbox1 = QVBoxLayout()
        r_vbox1.addLayout(r_grid1)
        r_vbox1.addWidget(self.editor)

        # Main Layout
        left_w = QWidget()
        left_w.setLayout(l_vbox1)
        right_w = QWidget()
        right_w.setLayout(r_vbox1)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(left_w)
        self.splitter.addWidget(right_w)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)


    def open_meta_file(self):
        ''' Opens .yml file containing metadata for NWB.'''
        filename, ftype = QFileDialog.getOpenFileName(None, 'Open file', '', "(*.yml)")
        if ftype=='(*.yml)':
            with open(filename) as f:
                data = yaml.safe_load(f)
            txt = yaml.dump(data, default_flow_style=False)
            self.editor.setText(txt)


    def save_meta_file(self):
        ''' Saves metadata to .yml file.'''
        pass


    def form_to_editor(self):
        """Loads data from form to editor."""
        data = {}
        data['General'] = self.box_general.read_fields()
        data['NWBFile'] = self.box_nwbfile.read_fields()

        txt = yaml.dump(data, default_flow_style=False)
        self.editor.setText(txt)


    def editor_to_form(self):
        """Loads data from editor to form."""
        pass
