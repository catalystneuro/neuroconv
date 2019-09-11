from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox)
from datetime import datetime


class GroupNwbfile(QGroupBox):
    def __init__(self, parent):
        """Groupbox for NWBFile fields filling form."""
        super().__init__()
        self.setTitle('NWBFile')

        self.lbl_session_description = QLabel('session_description:')
        self.lin_session_description = QLineEdit("session_description")
        self.lin_session_description.setToolTip("a description of the session where this data was generated")

        self.lbl_identifier = QLabel('identifier:')
        self.lin_identifier = QLineEdit("ABC123")
        self.lin_identifier.setToolTip("a unique text identifier for the file")

        self.lbl_session_start_time = QLabel('session_start_time:')
        self.lin_session_start_time1 = QLineEdit(datetime.now().strftime("%d/%m/%Y"))
        self.lin_session_start_time1.setToolTip("the start date and time of the recording session")
        self.lin_session_start_time2 = QLineEdit(datetime.now().strftime("%H:%M"))
        self.lin_session_start_time2.setToolTip("the start date and time of the recording session")

        self.lbl_experimenter = QLabel('experimenter:')
        self.lin_experimenter = QLineEdit('')
        self.lin_experimenter.setPlaceholderText("Alan Lloyd Hodgkin, Andrew Fielding Huxley")
        self.lin_experimenter.setToolTip("comma-separated list of names of persons who performed experiment")

        self.lbl_experiment_description = QLabel('experiment_description:')
        self.lin_experiment_description = QLineEdit('')
        self.lin_experiment_description.setPlaceholderText("propagation of action potentials in the squid giant axon")
        self.lin_experiment_description.setToolTip("general description of the experiment")

        self.lbl_session_id = QLabel('session_id:')
        self.lin_session_id = QLineEdit('')
        self.lin_session_id.setPlaceholderText("LAB 0123")
        self.lin_session_id.setToolTip("lab-specific ID for the session")

        self.lbl_institution = QLabel('institution:')
        self.lin_institution = QLineEdit('')
        self.lin_institution.setPlaceholderText("institution")
        self.lin_institution.setToolTip("institution(s) where experiment is performed")

        self.lbl_keywords = QLabel('keywords:')
        self.lin_keywords = QLineEdit('')
        self.lin_keywords.setPlaceholderText("action potential, ion channels, mathematical model")
        self.lin_keywords.setToolTip("comma-separated list of terms to search over")

        self.lbl_notes = QLabel("notes:")
        self.lin_notes = QLineEdit('')
        self.lin_notes.setPlaceholderText("Smells like a Nobel prize")
        self.lin_notes.setToolTip("Notes about the experiment")

        self.lbl_ = QLabel("")
        self.lin_ = QLineEdit('')
        self.lin_.setPlaceholderText("")
        self.lin_.setToolTip("")

        self.lbl_ = QLabel("")
        self.lin_ = QLineEdit('')
        self.lin_.setPlaceholderText("")
        self.lin_.setToolTip("")

        grid = QGridLayout()
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(4, 1)
        grid.addWidget(self.lbl_session_description, 0, 0, 1, 2)
        grid.addWidget(self.lin_session_description, 0, 2, 1, 4)
        grid.addWidget(self.lbl_identifier, 1, 0, 1, 2)
        grid.addWidget(self.lin_identifier, 1, 2, 1, 4)
        grid.addWidget(self.lbl_session_start_time, 2, 0, 1, 2)
        grid.addWidget(self.lin_session_start_time1, 2, 2, 1, 2)
        grid.addWidget(self.lin_session_start_time2, 2, 4, 1, 2)
        grid.addWidget(self.lbl_experimenter, 3, 0, 1, 2)
        grid.addWidget(self.lin_experimenter, 3, 2, 1, 4)
        grid.addWidget(self.lbl_experiment_description, 4, 0, 1, 2)
        grid.addWidget(self.lin_experiment_description, 4, 2, 1, 4)
        grid.addWidget(self.lbl_session_id, 5, 0, 1, 2)
        grid.addWidget(self.lin_session_id, 5, 2, 1, 4)
        grid.addWidget(self.lbl_institution, 6, 0, 1, 2)
        grid.addWidget(self.lin_institution, 6, 2, 1, 4)
        grid.addWidget(self.lbl_keywords, 7, 0, 1, 2)
        grid.addWidget(self.lin_keywords, 7, 2, 1, 4)
        grid.addWidget(self.lbl_notes, 8, 0, 1, 2)
        grid.addWidget(self.lin_notes, 8, 2, 1, 4)

        self.setLayout(grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['session_description'] = self.lin_session_description.text()
        data['identifier'] = self.lin_identifier.text()
        str_datetime = self.lin_session_start_time1.text()+", "+self.lin_session_start_time2.text()
        data['session_start_time'] = datetime.strptime(str_datetime,'%d/%m/%Y, %H:%M')
        experimenter = self.lin_experimenter.text()
        data['experimenter'] = [ex.strip() for ex in experimenter.split(',')]
        data['experiment_description'] = self.lin_experiment_description.text()
        data['session_id'] = self.lin_session_id.text()
        data['institution'] = self.lin_institution.text()
        keywords = self.lin_keywords.text()
        data['keywords'] = [kw.strip() for kw in keywords.split(',')]
        data['notes'] = self.lin_notes.text()
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
        self.grid.setColumnStretch(0, 0)
        self.grid.setColumnStretch(1, 0)
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_file_path, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_file_path, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_file_name, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_file_name, 1, 2, 1, 4)

        self.setLayout(self.grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['file_path'] = self.lin_file_path.text()
        data['file_name'] = self.lin_file_name.text()
        return data
