from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox)



class GroupNwbfile(QGroupBox):
    def __init__(self, parent):
        """Groupbox for NWBFile fields filling form."""
        super().__init__()
        self.setTitle('NWBFile')
        self.lbl_session_description = QLabel('session_description:')
        self.lin_session_description = QLineEdit('')
        self.lbl_identifier = QLabel('identifier:')
        self.lin_identifier = QLineEdit('')
        self.lbl_session_start_time = QLabel('session_start_time:')
        self.lin_session_start_time = QLineEdit('')
        self.lbl_file_create_date = QLabel('file_create_date:')
        self.lin_file_create_date = QLineEdit('')
        self.lbl_experimenter = QLabel('experimenter:')
        self.lin_experimenter = QLineEdit('')
        self.lbl_experiment_description = QLabel('experiment_description:')
        self.lin_experiment_description = QLineEdit('')
        self.lbl_session_id = QLabel('session_id:')
        self.lin_session_id = QLineEdit('')
        self.lbl_institution = QLabel('institution:')
        self.lin_institution = QLineEdit('')

        grid = QGridLayout()
        grid.addWidget(self.lbl_session_description, 0, 0, 1, 3)
        grid.addWidget(self.lin_session_description, 0, 3, 1, 3)
        grid.addWidget(self.lbl_identifier, 1, 0, 1, 3)
        grid.addWidget(self.lin_identifier, 1, 3, 1, 3)
        grid.addWidget(self.lbl_session_start_time, 2, 0, 1, 3)
        grid.addWidget(self.lin_session_start_time, 2, 3, 1, 3)
        grid.addWidget(self.lbl_file_create_date, 3, 0, 1, 3)
        grid.addWidget(self.lin_file_create_date, 3, 3, 1, 3)
        grid.addWidget(self.lbl_experimenter, 4, 0, 1, 3)
        grid.addWidget(self.lin_experimenter, 4, 3, 1, 3)
        grid.addWidget(self.lbl_experiment_description, 5, 0, 1, 3)
        grid.addWidget(self.lin_experiment_description, 5, 3, 1, 3)
        grid.addWidget(self.lbl_session_id, 6, 0, 1, 3)
        grid.addWidget(self.lin_session_id, 6, 3, 1, 3)
        grid.addWidget(self.lbl_institution, 7, 0, 1, 3)
        grid.addWidget(self.lin_institution, 7, 3, 1, 3)

        self.setLayout(grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['session_description'] = self.lin_session_description.text()
        data['identifier'] = self.lin_identifier.text()
        return data


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

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['file_path'] = self.lin_file_path.text()
        data['file_name'] = self.lin_file_name.text()
        return data
