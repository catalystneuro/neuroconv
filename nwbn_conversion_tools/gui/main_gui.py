from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication)
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
        pass

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
