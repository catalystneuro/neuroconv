from PyQt5.QtWidgets import (QLineEdit, QGridLayout, QLabel, QGroupBox,
                             QComboBox, QCheckBox)
from nwbn_conversion_tools.gui.utils.configs import required_asterisk_color
from datetime import datetime


class GroupNwbfile(QGroupBox):
    def __init__(self, parent):
        """Groupbox for NWBFile fields filling form."""
        super().__init__()
        self.parent = parent
        self.setTitle('NWBFile')
        self.group_type = 'NWBFile'

        self.lbl_session_description = QLabel('session_description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_session_description = QLineEdit("session_description")
        self.lin_session_description.setToolTip(
            "A description of the session where this data was generated")

        self.lbl_identifier = QLabel('identifier<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_identifier = QLineEdit("ABC123")
        self.lin_identifier.setToolTip("a unique text identifier for the file")

        self.lbl_session_start_time = QLabel('session_start_time<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_session_start_time1 = QLineEdit("")
        self.lin_session_start_time1.setPlaceholderText("dd/mm/yyyy")
        self.lin_session_start_time1.setToolTip("the start date and time of the recording session")
        self.lin_session_start_time2 = QLineEdit("")
        self.lin_session_start_time2.setPlaceholderText("hh:mm")
        self.lin_session_start_time2.setToolTip("the start date and time of the recording session")

        self.lbl_experimenter = QLabel('experimenter:')
        self.lin_experimenter = QLineEdit('')
        self.lin_experimenter.setPlaceholderText("Alan Lloyd Hodgkin, Andrew Fielding Huxley")
        self.lin_experimenter.setToolTip(
            "Comma-separated list of names of persons who performed experiment")

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
        self.lin_notes.setPlaceholderText("")
        self.lin_notes.setToolTip("Notes about the experiment")

        self.lbl_pharmacology = QLabel("pharmacology:")
        self.lin_pharmacology = QLineEdit('')
        self.lin_pharmacology.setPlaceholderText("")
        self.lin_pharmacology.setToolTip(
            "Description of drugs used, including how and when they were administered.\n"
            "Anesthesia(s), painkiller(s), etc., plus dosage, concentration, etc.")

        self.lbl_protocol = QLabel("protocol:")
        self.lin_protocol = QLineEdit('')
        self.lin_protocol.setPlaceholderText("")
        self.lin_protocol.setToolTip(
            "Experimental protocol, if applicable. E.g. include IACUC protocol")

        self.lbl_related_publications = QLabel("related publications:")
        self.lin_related_publications = QLineEdit('')
        self.lin_related_publications.setPlaceholderText("")
        self.lin_related_publications.setToolTip(
            "Publication information. PMID, DOI, URL, etc. If multiple, concatenate "
            "together \nand describe which is which")

        self.lbl_slices = QLabel("slices:")
        self.lin_slices = QLineEdit('')
        self.lin_slices.setPlaceholderText("")
        self.lin_slices.setToolTip(
            "Description of slices, including information about preparation thickness,"
            "\norientation, temperature and bath solution")

        self.lbl_data_collection = QLabel("data_collection:")
        self.lin_data_collection = QLineEdit('')
        self.lin_data_collection.setPlaceholderText("")
        self.lin_data_collection.setToolTip("Notes about data collection and analysis")

        self.lbl_surgery = QLabel("surgery:")
        self.lin_surgery = QLineEdit('')
        self.lin_surgery.setPlaceholderText("")
        self.lin_surgery.setToolTip(
            "Narrative description about surgery/surgeries, including date(s) and who performed surgery.")

        self.lbl_virus = QLabel("virus:")
        self.lin_virus = QLineEdit('')
        self.lin_virus.setPlaceholderText("")
        self.lin_virus.setToolTip(
            "Information about virus(es) used in experiments, including virus ID, source, "
            "date made, injection location, volume, etc.")

        self.lbl_stimulus_notes = QLabel("stimulus_notes:")
        self.lin_stimulus_notes = QLineEdit('')
        self.lin_stimulus_notes.setPlaceholderText("")
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
        grid.addWidget(self.lbl_related_publications, 12, 0, 1, 2)
        grid.addWidget(self.lin_related_publications, 12, 2, 1, 4)
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
        try:
            data['session_start_time'] = datetime.strptime(str_datetime, '%d/%m/%Y, %H:%M')
        except Exception as error:
            data['session_start_time'] = datetime.now()
            self.parent.write_to_logger(str(error))
            self.parent.write_to_logger("WARNING: Invalid 'session_start_time' format. "
                                        "Default to current datetime.")
        data['experimenter'] = self.lin_experimenter.text()
        data['experiment_description'] = self.lin_experiment_description.text()
        data['session_id'] = self.lin_session_id.text()
        data['institution'] = self.lin_institution.text()
        data['lab'] = self.lin_lab.text()
        keywords = self.lin_keywords.text()
        data['keywords'] = [kw.strip() for kw in keywords.split(',')]
        data['notes'] = self.lin_notes.text()
        data['pharmacology'] = self.lin_pharmacology.text()
        data['protocol'] = self.lin_protocol.text()
        data['related_publications'] = self.lin_related_publications.text()
        data['slices'] = self.lin_slices.text()
        data['data_collection'] = self.lin_data_collection.text()
        data['surgery'] = self.lin_surgery.text()
        data['virus'] = self.lin_virus.text()
        data['stimulus_notes'] = self.lin_stimulus_notes.text()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_session_description.setText(data['session_description'])
        self.lin_identifier.setText(data['identifier'])
        if 'session_start_time' in data and data['session_start_time']:
            str_datetime = data['session_start_time'].strftime('%d/%m/%Y, %H:%M')
            self.lin_session_start_time1.setText(str_datetime.split(',')[0])
            self.lin_session_start_time2.setText(str_datetime.split(',')[1].strip())
        if 'experimenter' in data:
            self.lin_experimenter.setText(data['experimenter'])
        if 'experiment_description' in data:
            self.lin_experiment_description.setText(data['experiment_description'])
        if 'session_id' in data:
            self.lin_session_id.setText(data['session_id'])
        if 'institution' in data:
            self.lin_institution.setText(data['institution'])
        if 'lab' in data:
            self.lin_lab.setText(data['lab'])
        if 'keywords' in data and data['keywords'] is not None:
            self.lin_keywords.setText(','.join(str(x) for x in data['keywords']))
        if 'notes' in data:
            self.lin_notes.setText(data['notes'])
        if 'pharmacology' in data:
            self.lin_pharmacology.setText(data['pharmacology'])
        if 'protocol' in data:
            self.lin_protocol.setText(data['protocol'])
        if 'related_publications' in data:
            self.lin_related_publications.setText(data['related_publications'])
        if 'slices' in data:
            self.lin_slices.setText(data['slices'])
        if 'data_collection' in data:
            self.lin_data_collection.setText(data['data_collection'])
        if 'surgery' in data:
            self.lin_surgery.setText(data['surgery'])
        if 'virus' in data:
            self.lin_virus.setText(data['virus'])
        if 'stimulus_notes' in data:
            self.lin_stimulus_notes.setText(data['stimulus_notes'])


class GroupSubject(QGroupBox):
    def __init__(self, parent):
        """Groupbox for 'pynwb.file.Subject' fields filling form."""
        super().__init__()
        self.setTitle('Subject')
        self.group_type = 'Subject'

        self.lbl_age = QLabel('age:')
        self.lin_age = QLineEdit('')
        self.lin_age.setPlaceholderText("age")
        self.lin_age.setToolTip("the age of the subject")

        self.lbl_description = QLabel('description:')
        self.lin_description = QLineEdit('')
        self.lin_description.setPlaceholderText("description")
        self.lin_description.setToolTip("a description of the subject")

        self.lbl_genotype = QLabel('genotype:')
        self.lin_genotype = QLineEdit('')
        self.lin_genotype.setPlaceholderText("genotype")
        self.lin_genotype.setToolTip("the genotype of the subject")

        self.lbl_sex = QLabel('sex:')
        self.lin_sex = QLineEdit('')
        self.lin_sex.setPlaceholderText("sex")
        self.lin_sex.setToolTip("the sex of the subject")

        self.lbl_species = QLabel('species:')
        self.lin_species = QLineEdit('')
        self.lin_species.setPlaceholderText("species")
        self.lin_species.setToolTip("the species of the subject")

        self.lbl_subject_id = QLabel('subject_id:')
        self.lin_subject_id = QLineEdit('')
        self.lin_subject_id.setPlaceholderText("subject_id")
        self.lin_subject_id.setToolTip("a unique identifier for the subject")

        self.lbl_weight = QLabel('weight:')
        self.lin_weight = QLineEdit('')
        self.lin_weight.setPlaceholderText("weight")
        self.lin_weight.setToolTip("the weight of the subject")

        self.lbl_date_of_birth = QLabel('date_of_birth:')
        self.lin_date_of_birth = QLineEdit('')
        self.lin_date_of_birth.setPlaceholderText(datetime.now().strftime("%d/%m/%Y"))
        self.lin_date_of_birth.setToolTip(
            "datetime of date of birth. May be supplied instead of age.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_age, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_age, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_genotype, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_genotype, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_sex, 3, 0, 1, 2)
        self.grid.addWidget(self.lin_sex, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_species, 4, 0, 1, 2)
        self.grid.addWidget(self.lin_species, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_subject_id, 5, 0, 1, 2)
        self.grid.addWidget(self.lin_subject_id, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_weight, 6, 0, 1, 2)
        self.grid.addWidget(self.lin_weight, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_date_of_birth, 7, 0, 1, 2)
        self.grid.addWidget(self.lin_date_of_birth, 7, 2, 1, 4)

        self.setLayout(self.grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['age'] = self.lin_age.text()
        data['description'] = self.lin_description.text()
        data['genotype'] = self.lin_genotype.text()
        data['sex'] = self.lin_sex.text()
        data['species'] = self.lin_species.text()
        data['subject_id'] = self.lin_subject_id.text()
        data['weight'] = self.lin_weight.text()
        str_datetime = self.lin_date_of_birth.text()
        if len(str_datetime) > 0:
            data['date_of_birth'] = datetime.strptime(str_datetime, '%d/%m/%Y')
        else:
            data['date_of_birth'] = ''
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        if 'age' in data:
            self.lin_age.setText(data['age'])
        if 'description' in data:
            self.lin_description.setText(data['description'])
        if 'genotype' in data:
            self.lin_genotype.setText(data['genotype'])
        if 'sex' in data:
            self.lin_sex.aetText(data['sex'])
        if 'species' in data:
            self.lin_species.setText(data['species'])
        if 'subject_id' in data:
            self.lin_subject_id.setText(data['subject_id'])
        if 'weight' in data:
            self.lin_weight.setText(data['weight'])
        if 'date_of_birth' in data:
            self.lin_date_of_birth.setText(data['date_of_birth'].strftime("%d/%m/%Y"))


class GroupDevice(QGroupBox):
    def __init__(self, parent):
        """Groupbox for pynwb.device.Device fields filling form."""
        super().__init__()
        self.setTitle('Device')
        self.parent = parent
        self.group_type = 'Device'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('Device')
        self.lin_name.setToolTip("the name pof this device")
        nDevices = 0
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupDevice):
                nDevices += 1
        if nDevices > 0:
            self.lin_name.setText('Device'+str(nDevices))

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)

        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])


class GroupCustomExample(QGroupBox):
    def __init__(self, parent):
        """
        Groupbox for to serve as example for creation of custom groups.
        Don't forget to add this class to the relevant handling functions at the
        parent, e.g. add_group()
        """
        super().__init__()
        self.setTitle('CustomName')
        self.parent = parent
        self.group_type = 'CustomName'

        # Name: it has a special treatment, since it need to be unique we test
        # if the parent contain other objects of the same type
        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_name = QLineEdit('CustomName')
        self.lin_name.setToolTip("The unique name of this group.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupCustomExample):
                nInstances += 1
        if nInstances > 0:
            self.lin_name.setText('CustomName'+str(nInstances))

        # Mandatory field: we fill it with default values
        self.lbl_mandatory = QLabel('mandatory<span style="color:'+required_asterisk_color+';">*</span>:')
        self.lin_mandatory = QLineEdit('ABC123')
        self.lin_mandatory.setToolTip("This is a mandatory field.")

        # Optional field: we leave a placeholder text as example
        self.lbl_optional = QLabel('optional:')
        self.lin_optional = QLineEdit('')
        self.lin_optional.setPlaceholderText("example")
        self.lin_optional.setToolTip("This is an optional field.")

        # Field with link to other objects. This type of field needs to be
        # updated with self.refresh_objects_references()
        self.lbl_link = QLabel('link:')
        self.combo_link = CustomComboBox()
        self.combo_link.setToolTip("This field links to existing objects.")

        # Field that should be handled by conversion script
        self.lbl_script = QLabel('script:')
        self.chk_script = QCheckBox("Get from source file")
        self.chk_script.setChecked(False)
        self.chk_script.setToolTip(
            "This field will be handled by conversion script.\n"
            "Check box if this data will be retrieved from source file.\n"
            "Uncheck box to ignore it.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.lin_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_mandatory, 1, 0, 1, 2)
        self.grid.addWidget(self.lin_mandatory, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_optional, 2, 0, 1, 2)
        self.grid.addWidget(self.lin_optional, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_link, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_link, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_script, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_script, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self):
        """Refreshes references with existing objects in parent group."""
        self.combo_link.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCustomExample):
                self.combo_link.addItem(grp.lin_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.lin_name.text()
        data['mandatory'] = self.lin_mandatory.text()
        data['optional'] = self.lin_optional.text()
        data['link'] = self.combo_link.currentText()
        if self.chk_script.isChecked():
            data['script'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.lin_name.setText(data['name'])
        self.lin_mandatory.setText(data['mandatory'])
        if 'optional' in data:
            self.lin_optional.setText(data['optional'])
        self.combo_link.clear()
        self.combo_link.addItem(data['link'])
        if 'script' in data:
            self.chk_script.setChecked(True)


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
