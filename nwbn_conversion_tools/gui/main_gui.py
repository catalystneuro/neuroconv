from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
    QTabWidget, QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QLabel, QFileDialog, QGroupBox, QMessageBox)
from nwbn_conversion_tools.gui.classes.tabs import TabMetafile
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
        action_meta_data.triggered.connect(self.make_tab_meta_file)
        action_func2 = QAction('Convert X to NWB', self)
        toolsMenu.addAction(action_func2)
        #action_load_intervals.triggered.connect(self.func)

        helpMenu = mainMenu.addMenu('Help')
        action_about = QAction('About', self)
        helpMenu.addAction(action_about)
        action_about.triggered.connect(self.about)

        # Center panels -------------------------------------------------------
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)


    def make_tab_meta_file(self):
        """Makes a new Metadata file tab."""
        tab = TabMetafile(self)
        self.new_tab(tab_object=tab, title='Metadata')


    def new_tab(self, tab_object, title):
        """Opens new tab."""
        self.tabs.addTab(tab_object, title)


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
