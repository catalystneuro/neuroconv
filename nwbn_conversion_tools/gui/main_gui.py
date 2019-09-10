from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
    QTabWidget, QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QLabel, QFileDialog)
import numpy as np
import os
import sys


class Application(QMainWindow):
    def __init__(self):
        super().__init__()

        self.centralwidget = QWidget()
        self.setCentralWidget(self.centralwidget)
        self.resize(1200, 900)
        self.setWindowTitle('NWB')

        #Initialize GUI elements
        self.init_gui()
        self.show()


    def init_gui(self):
        """Initiates GUI elements."""
        mainMenu = self.menuBar()
        # File menu
        fileMenu = mainMenu.addMenu('File')
        # Adding actions to file menu
        action_open_file = QAction('Open File', self)
        fileMenu.addAction(action_open_file)
        #action_open_file.triggered.connect(lambda: self.open_file(None))

        toolsMenu = mainMenu.addMenu('Tools')
        action_meta_data = QAction('Meta-data', self)
        toolsMenu.addAction(action_meta_data)
        action_meta_data.triggered.connect(self.make_tab_meta_data)
        action_func2 = QAction('Convert X to NWB', self)
        toolsMenu.addAction(action_func2)
        #action_load_intervals.triggered.connect(self.func)

        helpMenu = mainMenu.addMenu('Help')
        action_about = QAction('About', self)
        helpMenu.addAction(action_about)
        #action_about.triggered.connect(self.about)

        # Center panels -------------------------------------------------------
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)


    def make_tab_meta_data(self):
        """Opens new tab for Meta-data file editing."""
        self.tab1 = QWidget()
        self.tabs.addTab(self.tab1, "Meta-data")
        self.tab1.layout = QSplitter(Qt.Horizontal)

        # Left-side panel: forms
        btn_load_meta = QPushButton('Load from file')
        btn_load_meta.clicked.connect(lambda: self.open_meta_file())
        btn_save_meta = QPushButton('Save to file')
        btn_save_meta.clicked.connect(lambda: self.save_meta_file())
        label1 = QLabel('Something:')
        line1 = QLineEdit('User enter here')
        label2 = QLabel('Something else:')
        line2 = QLineEdit('User enter here')

        grid1 = QGridLayout()
        grid1.addWidget(btn_load_meta, 0, 0, 1, 3)
        grid1.addWidget(btn_save_meta, 0, 3, 1, 3)
        grid1.addWidget(QLabel(), 1, 0, 1, 6)
        grid1.addWidget(label1, 2, 0, 1, 3)
        grid1.addWidget(line1, 2, 3, 1, 3)
        grid1.addWidget(label2, 3, 0, 1, 3)
        grid1.addWidget(line2, 3, 3, 1, 3)

        vbox1 = QVBoxLayout()
        vbox1.addLayout(grid1)
        vbox1.addStretch()

        # Right-side panel: meta-data text
        vbox2 = QVBoxLayout()
        r_label1 = QLabel('Resulting meta-data file:')
        self.text1 = QTextEdit()
        vbox2.addWidget(r_label1)
        vbox2.addWidget(self.text1)

        # Main Layout
        left_w = QWidget()
        left_w.setLayout(vbox1)
        right_w = QWidget()
        right_w.setLayout(vbox2)
        self.tab1.layout.addWidget(left_w)
        self.tab1.layout.addWidget(right_w)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab1.layout)
        self.tab1.setLayout(main_layout)


    def open_meta_file(self):
        ''' Opens .txt file containing metadata for NWB.'''
        filename, ftype = QFileDialog.getOpenFileName(None, 'Open file', '', "(*.txt)")
        if ftype=='(*.txt)':
            f = open(filename, "r")
            txt = f.read()
            f.close()
            self.text1.setText(txt)


    def save_meta_file(self):
        ''' Saves metadata to .txt file.'''
        pass


    def closeEvent(self, event):
        """Before exiting, executes these actions."""
        event.accept()




if __name__ == '__main__':
    app = QApplication(sys.argv)  #instantiate a QtGui (holder for the app)
    #if len(sys.argv)==1:
    #    fname = None
    #else:
    #    fname = sys.argv[1]
    ex = Application()
    sys.exit(app.exec_())


def main(filename=None):  # If it was imported as a module
    """Sets up QT application."""
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)  #instantiate a QtGui (holder for the app)
    ex = Application()
    sys.exit(app.exec_())
