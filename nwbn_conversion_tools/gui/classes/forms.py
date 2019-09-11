from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QAction, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QGroupBox)
from datetime import datetime


class GroupGeneral(QGroupBox):
    def __init__(self, parent):
        """Groupbox for General fields filling form."""
        super().__init__()
        self.setTitle('General')
        self.group_name = 'general'

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



class GroupOphys(QGroupBox):
    def __init__(self, parent):
        """Groupbox for General fields filling form."""
        super().__init__()
        self.setTitle('Ophys')
        self.group_name = 'ophys'

        self.lbl_f1 = QLabel('field1:')
        self.lin_f1 = QLineEdit('')
        self.lin_f1.setPlaceholderText("field_name")
        self.lin_f1.setToolTip("tooltip")

        self.lbl_f2 = QLabel('field2:')
        self.lin_f2 = QLineEdit('')
        self.lin_f2.setPlaceholderText("field_name")
        self.lin_f2.setToolTip("tooltip")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_f1, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_f1, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_f2, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_f2, 1, 2, 1, 4)

        self.setLayout(self.grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['f1'] = self.lin_f1.text()
        data['f2'] = self.lin_f2.text()
        return data



class GroupNwbfile(QGroupBox):
    def __init__(self, parent):
        """Groupbox for NWBFile fields filling form."""
        super().__init__()
        self.setTitle('NWBFile')
        self.group_name = 'nwbfile'

        self.lbl_session_description = QLabel('session_description:')
        self.lin_session_description = QLineEdit("session_description")
        self.lin_session_description.setToolTip("a description of the session where "
            "this data was generated")

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
        self.lin_experimenter.setToolTip("comma-separated list of names of persons "
            "who performed experiment")

        self.lbl_experiment_description = QLabel('experiment_description:')
        self.lin_experiment_description = QLineEdit('')
        self.lin_experiment_description.setPlaceholderText("propagation of action "
            "potentials in the squid giant axon")
        self.lin_experiment_description.setToolTip("general description of the experiment")

        self.lbl_session_id = QLabel('session_id:')
        self.lin_session_id = QLineEdit('')
        self.lin_session_id.setPlaceholderText("LAB 0123")
        self.lin_session_id.setToolTip("lab-specific ID for the session")

        self.lbl_institution = QLabel('institution:')
        self.lin_institution = QLineEdit('')
        self.lin_institution.setPlaceholderText("institution")
        self.lin_institution.setToolTip("institution(s) where experiment is performed")

        self.lbl_lab = QLabel("lab:")
        self.lin_lab = QLineEdit('')
        self.lin_lab.setPlaceholderText("lab name")
        self.lin_lab.setToolTip("lab where experiment was performed")

        self.lbl_keywords = QLabel('keywords:')
        self.lin_keywords = QLineEdit('')
        self.lin_keywords.setPlaceholderText("action potential, ion channels, mathematical model")
        self.lin_keywords.setToolTip("comma-separated list of terms to search over")

        self.lbl_notes = QLabel("notes:")
        self.lin_notes = QLineEdit('')
        self.lin_notes.setPlaceholderText("Smells like a Nobel prize")
        self.lin_notes.setToolTip("Notes about the experiment")

        self.lbl_pharmacology = QLabel("pharmacology:")
        self.lin_pharmacology = QLineEdit('')
        self.lin_pharmacology.setPlaceholderText("pharmacology")
        self.lin_pharmacology.setToolTip("Description of drugs used, including how "
            "and when they were administered.\nAnesthesia(s), painkiller(s), etc., "
            "plus dosage, concentration, etc.")

        self.lbl_protocol = QLabel("protocol:")
        self.lin_protocol = QLineEdit('')
        self.lin_protocol.setPlaceholderText("protocol")
        self.lin_protocol.setToolTip("Experimental protocol, if applicable. E.g."
            " include IACUC protocol")

        self.lbl_related_pubications = QLabel("related pubications:")
        self.lin_related_pubications = QLineEdit('')
        self.lin_related_pubications.setPlaceholderText("related_pubications")
        self.lin_related_pubications.setToolTip("Publication information. PMID,"
            " DOI, URL, etc. If multiple, concatenate together \nand describe"
            " which is which")

        self.lbl_slices = QLabel("slices:")
        self.lin_slices = QLineEdit('')
        self.lin_slices.setPlaceholderText("slices")
        self.lin_slices.setToolTip("Description of slices, including information "
            "about preparation thickness, \norientation, temperature and bath solution")

        self.lbl_data_collection = QLabel("data_collection:")
        self.lin_data_collection = QLineEdit('')
        self.lin_data_collection.setPlaceholderText("data collection")
        self.lin_data_collection.setToolTip("Notes about data collection and analysis")

        self.lbl_surgery = QLabel("surgery:")
        self.lin_surgery = QLineEdit('')
        self.lin_surgery.setPlaceholderText("surgery")
        self.lin_surgery.setToolTip("Narrative description about surgery/surgeries, "
            "including date(s) and who performed surgery.")

        self.lbl_virus = QLabel("virus:")
        self.lin_virus = QLineEdit('')
        self.lin_virus.setPlaceholderText("virus")
        self.lin_virus.setToolTip("Information about virus(es) used in experiments, "
            "including virus ID, source, date made, injection location, volume, etc.")

        self.lbl_stimulus_notes = QLabel("stimulus_notes:")
        self.lin_stimulus_notes = QLineEdit('')
        self.lin_stimulus_notes.setPlaceholderText("stimulus notes")
        self.lin_stimulus_notes.setToolTip("Notes about stimuli, such as how and where presented.")

        grid = QGridLayout()
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
        grid.addWidget(self.lbl_lab, 7, 0, 1, 2)
        grid.addWidget(self.lin_lab, 7, 2, 1, 4)
        grid.addWidget(self.lbl_keywords, 8, 0, 1, 2)
        grid.addWidget(self.lin_keywords, 8, 2, 1, 4)
        grid.addWidget(self.lbl_notes, 9, 0, 1, 2)
        grid.addWidget(self.lin_notes, 9, 2, 1, 4)
        grid.addWidget(self.lbl_pharmacology, 10, 0, 1, 2)
        grid.addWidget(self.lin_pharmacology, 10, 2, 1, 4)
        grid.addWidget(self.lbl_protocol, 11, 0, 1, 2)
        grid.addWidget(self.lin_protocol, 11, 2, 1, 4)
        grid.addWidget(self.lbl_related_pubications, 12, 0, 1, 2)
        grid.addWidget(self.lin_related_pubications, 12, 2, 1, 4)
        grid.addWidget(self.lbl_slices, 13, 0, 1, 2)
        grid.addWidget(self.lin_slices, 13, 2, 1, 4)
        grid.addWidget(self.lbl_data_collection, 14, 0, 1, 2)
        grid.addWidget(self.lin_data_collection, 14, 2, 1, 4)
        grid.addWidget(self.lbl_surgery, 15, 0, 1, 2)
        grid.addWidget(self.lin_surgery, 15, 2, 1, 4)
        grid.addWidget(self.lbl_virus, 16, 0, 1, 2)
        grid.addWidget(self.lin_virus, 16, 2, 1, 4)
        grid.addWidget(self.lbl_stimulus_notes, 17, 0, 1, 2)
        grid.addWidget(self.lin_stimulus_notes, 17, 2, 1, 4)

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
        data['lab'] = self.lin_lab.text()
        keywords = self.lin_keywords.text()
        data['keywords'] = [kw.strip() for kw in keywords.split(',')]
        data['notes'] = self.lin_notes.text()
        data['pharmacology'] = self.lin_pharmacology.text()
        data['protocol'] = self.lin_protocol.text()
        data['related_pubications'] = self.lin_related_pubications.text()
        data['slices'] = self.lin_slices.text()
        data['data_collection'] = self.lin_data_collection.text()
        data['surgery'] = self.lin_surgery.text()
        data['virus'] = self.lin_virus.text()
        data['stimulus_notes'] = self.lin_stimulus_notes.text()
        return data
