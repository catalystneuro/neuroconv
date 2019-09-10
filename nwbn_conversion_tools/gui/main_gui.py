from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
    QTabWidget, QPushButton, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout)
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
        self.tab1.layout = QHBoxLayout()

        # Left-side panel: forms
        vbox1 = QVBoxLayout()
        push1 = QPushButton('Do something')
        line1 = QLineEdit('User enter here')
        vbox1.addWidget(push1)
        vbox1.addWidget(line1)

        # Right-side panel: meta-data text
        vbox2 = QVBoxLayout()
        text1 = QTextEdit()
        vbox2.addWidget(text1)

        # Main Layout
        self.tab1.layout.addLayout(vbox1)
        self.tab1.layout.addLayout(vbox2)
        self.tab1.setLayout(self.tab1.layout)


    def open_meta_file(self, filename):
        ''' Opens .txt file containing metadata for NWB.'''
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
