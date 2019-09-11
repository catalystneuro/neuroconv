from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox)



class GroupNwbfile(QGroupBox):
    def __init__(self, parent):
        """Groupbox for NWBFile fields filling form."""
        super().__init__()
        self.setTitle('NWBFile')
        lbl_session_description = QLabel('session_description:')
        lin_session_description = QLineEdit('')
        lbl_identifier = QLabel('identifier:')
        lin_identifier = QLineEdit('')
        lbl_session_start_time = QLabel('session_start_time:')
        lin_session_start_time = QLineEdit('')
        lbl_file_create_date = QLabel('file_create_date:')
        lin_file_create_date = QLineEdit('')
        lbl_experimenter = QLabel('experimenter:')
        lin_experimenter = QLineEdit('')
        lbl_experiment_description = QLabel('experiment_description:')
        lin_experiment_description = QLineEdit('')
        lbl_session_id = QLabel('session_id:')
        lin_session_id = QLineEdit('')
        lbl_institution = QLabel('institution:')
        lin_institution = QLineEdit('')

        grid = QGridLayout()
        grid.addWidget(lbl_session_description, 0, 0, 1, 3)
        grid.addWidget(lin_session_description, 0, 3, 1, 3)
        grid.addWidget(lbl_identifier, 1, 0, 1, 3)
        grid.addWidget(lin_identifier, 1, 3, 1, 3)
        grid.addWidget(lbl_session_start_time, 2, 0, 1, 3)
        grid.addWidget(lin_session_start_time, 2, 3, 1, 3)
        grid.addWidget(lbl_file_create_date, 3, 0, 1, 3)
        grid.addWidget(lin_file_create_date, 3, 3, 1, 3)
        grid.addWidget(lbl_experimenter, 4, 0, 1, 3)
        grid.addWidget(lin_experimenter, 4, 3, 1, 3)
        grid.addWidget(lbl_experiment_description, 5, 0, 1, 3)
        grid.addWidget(lin_experiment_description, 5, 3, 1, 3)
        grid.addWidget(lbl_session_id, 6, 0, 1, 3)
        grid.addWidget(lin_session_id, 6, 3, 1, 3)
        grid.addWidget(lbl_institution, 7, 0, 1, 3)
        grid.addWidget(lin_institution, 7, 3, 1, 3)

        self.setLayout(grid)


class GroupGeneral(QGroupBox):
    def __init__(self, parent):
        """Groupbox for General fields filling form."""
        super().__init__()
        self.setTitle('General')
        self.lbl_file_path = QLabel('file_path:')
        self.lin_file_path = QLineEdit('')
        self.lbl_file_name = QLabel('file_name:')
        self.lin_file_name = QLineEdit('')

        self.grid = QGridLayout()
        self.grid.addWidget(self.lbl_file_path, 0, 0, 1, 3)
        self.grid.addWidget(self.lin_file_path, 0, 3, 1, 3)
        self.grid.addWidget(self.lbl_file_name, 1, 0, 1, 3)
        self.grid.addWidget(self.lin_file_name, 1, 3, 1, 3)

        self.setLayout(self.grid)
