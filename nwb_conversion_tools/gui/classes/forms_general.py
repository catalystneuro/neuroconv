from PySide2.QtGui import QIntValidator, QDoubleValidator
from PySide2.QtWidgets import (QLineEdit, QGridLayout, QLabel, QGroupBox,
                             QComboBox, QCheckBox)
from nwb_conversion_tools.gui.utils.configs import required_asterisk_color
from nwb_conversion_tools.gui.classes.collapsible_box import CollapsibleBox

from datetime import datetime
import numpy as np
import pynwb


#class GroupNwbfile(QGroupBox):
class GroupNwbfile(CollapsibleBox):
    def __init__(self, parent, metadata):
        """Groupbox for NWBFile fields filling form."""
        super().__init__(title="NWBFile", parent=parent)
        self.parent = parent
        self.metadata = metadata
        #self.setTitle('NWBFile')
        self.group_type = 'NWBFile'
        self.groups_list = []

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.setColumnStretch(4, 1)

        self.lbl_session_description = QLabel('session_description<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_session_description = QLineEdit("session_description")
        self.form_session_description.setToolTip(
            "A description of the session where this data was generated")
        self.grid.addWidget(self.lbl_session_description, 0, 0, 1, 2)
        self.grid.addWidget(self.form_session_description, 0, 2, 1, 4)

        self.lbl_identifier = QLabel('identifier<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_identifier = QLineEdit("ABC123")
        self.form_identifier.setToolTip("a unique text identifier for the file")
        self.grid.addWidget(self.lbl_identifier, 1, 0, 1, 2)
        self.grid.addWidget(self.form_identifier, 1, 2, 1, 4)

        self.lbl_session_start_time = QLabel('session_start_time<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_session_start_time1 = QLineEdit("")
        self.form_session_start_time1.setPlaceholderText("dd/mm/yyyy")
        self.form_session_start_time1.setToolTip("the start date and time of the recording session")
        self.form_session_start_time2 = QLineEdit("")
        self.form_session_start_time2.setPlaceholderText("hh:mm")
        self.form_session_start_time2.setToolTip("the start date and time of the recording session")
        self.grid.addWidget(self.lbl_session_start_time, 2, 0, 1, 2)
        self.grid.addWidget(self.form_session_start_time1, 2, 2, 1, 2)
        self.grid.addWidget(self.form_session_start_time2, 2, 4, 1, 2)

        self.lbl_experimenter = QLabel('experimenter:')
        self.form_experimenter = QLineEdit('')
        self.form_experimenter.setPlaceholderText("Alan Lloyd Hodgkin, Andrew Fielding Huxley")
        self.form_experimenter.setToolTip(
            "Comma-separated list of names of persons who performed experiment")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_experimenter, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_experimenter, nWidgetsGrid, 2, 1, 4)

        self.lbl_experiment_description = QLabel('experiment_description:')
        self.form_experiment_description = QLineEdit('')
        self.form_experiment_description.setPlaceholderText("propagation of action potentials in the squid giant axon")
        self.form_experiment_description.setToolTip("general description of the experiment")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_experiment_description, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_experiment_description, nWidgetsGrid, 2, 1, 4)

        self.lbl_session_id = QLabel('session_id:')
        self.form_session_id = QLineEdit('')
        self.form_session_id.setPlaceholderText("LAB 0123")
        self.form_session_id.setToolTip("lab-specific ID for the session")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_session_id, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_session_id, nWidgetsGrid, 2, 1, 4)

        self.lbl_institution = QLabel('institution:')
        self.form_institution = QLineEdit('')
        self.form_institution.setPlaceholderText("institution")
        self.form_institution.setToolTip("institution(s) where experiment is performed")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_institution, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_institution, nWidgetsGrid, 2, 1, 4)

        self.lbl_lab = QLabel("lab:")
        self.form_lab = QLineEdit('')
        self.form_lab.setPlaceholderText("lab name")
        self.form_lab.setToolTip("lab where experiment was performed")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_lab, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_lab, nWidgetsGrid, 2, 1, 4)

        if 'lab_meta_data' in metadata.keys():
            self.lbl_lab_meta_data = QLabel("lab_meta_data:")
            self.lab_meta_data = GroupCustomExtension(parent=self, metadata=metadata['lab_meta_data'])
            self.lab_meta_data.setToolTip("an extension that contains lab-specific meta-data")
            nWidgetsGrid = self.grid.rowCount()
            self.grid.addWidget(self.lbl_lab_meta_data, nWidgetsGrid, 0, 1, 2)
            self.grid.addWidget(self.lab_meta_data, nWidgetsGrid, 2, 1, 4)

        self.lbl_keywords = QLabel('keywords:')
        self.form_keywords = QLineEdit('')
        self.form_keywords.setPlaceholderText("action potential, ion channels, mathematical model")
        self.form_keywords.setToolTip("comma-separated list of terms to search over")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_keywords, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_keywords, nWidgetsGrid, 2, 1, 4)

        self.lbl_notes = QLabel("notes:")
        self.form_notes = QLineEdit('')
        self.form_notes.setPlaceholderText("")
        self.form_notes.setToolTip("Notes about the experiment")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_notes, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_notes, nWidgetsGrid, 2, 1, 4)

        self.lbl_pharmacology = QLabel("pharmacology:")
        self.form_pharmacology = QLineEdit('')
        self.form_pharmacology.setPlaceholderText("")
        self.form_pharmacology.setToolTip(
            "Description of drugs used, including how and when they were administered.\n"
            "Anesthesia(s), painkiller(s), etc., plus dosage, concentration, etc.")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_pharmacology, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_pharmacology, nWidgetsGrid, 2, 1, 4)

        self.lbl_protocol = QLabel("protocol:")
        self.form_protocol = QLineEdit('')
        self.form_protocol.setPlaceholderText("")
        self.form_protocol.setToolTip(
            "Experimental protocol, if applicable. E.g. include IACUC protocol")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_protocol, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_protocol, nWidgetsGrid, 2, 1, 4)

        self.lbl_related_publications = QLabel("related publications:")
        self.form_related_publications = QLineEdit('')
        self.form_related_publications.setPlaceholderText("")
        self.form_related_publications.setToolTip(
            "Publication information. PMID, DOI, URL, etc. If multiple, concatenate "
            "together \nand describe which is which")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_related_publications, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_related_publications, nWidgetsGrid, 2, 1, 4)

        self.lbl_slices = QLabel("slices:")
        self.form_slices = QLineEdit('')
        self.form_slices.setPlaceholderText("")
        self.form_slices.setToolTip(
            "Description of slices, including information about preparation thickness,"
            "\norientation, temperature and bath solution")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_slices, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_slices, nWidgetsGrid, 2, 1, 4)

        self.lbl_data_collection = QLabel("data_collection:")
        self.form_data_collection = QLineEdit('')
        self.form_data_collection.setPlaceholderText("")
        self.form_data_collection.setToolTip("Notes about data collection and analysis")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_data_collection, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_data_collection, nWidgetsGrid, 2, 1, 4)

        self.lbl_surgery = QLabel("surgery:")
        self.form_surgery = QLineEdit('')
        self.form_surgery.setPlaceholderText("")
        self.form_surgery.setToolTip(
            "Narrative description about surgery/surgeries, including date(s) and who performed surgery.")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_surgery, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_surgery, nWidgetsGrid, 2, 1, 4)

        self.lbl_virus = QLabel("virus:")
        self.form_virus = QLineEdit('')
        self.form_virus.setPlaceholderText("")
        self.form_virus.setToolTip(
            "Information about virus(es) used in experiments, including virus ID, source, "
            "date made, injection location, volume, etc.")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_virus, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_virus, nWidgetsGrid, 2, 1, 4)

        self.lbl_stimulus_notes = QLabel("stimulus_notes:")
        self.form_stimulus_notes = QLineEdit('')
        self.form_stimulus_notes.setPlaceholderText("")
        self.form_stimulus_notes.setToolTip("Notes about stimuli, such as how and where presented.")
        nWidgetsGrid = self.grid.rowCount()
        self.grid.addWidget(self.lbl_stimulus_notes, nWidgetsGrid, 0, 1, 2)
        self.grid.addWidget(self.form_stimulus_notes, nWidgetsGrid, 2, 1, 4)
        #self.setLayout(self.grid)
        self.setContentLayout(self.grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        error = None
        data = {}
        data['session_description'] = self.form_session_description.text()
        data['identifier'] = self.form_identifier.text()
        str_datetime = self.form_session_start_time1.text()+", "+self.form_session_start_time2.text()
        try:
            data['session_start_time'] = datetime.strptime(str_datetime, '%d/%m/%Y, %H:%M')
        except Exception as error:
            self.parent.write_to_logger(str(error))
            self.parent.write_to_logger("ERROR: Invalid 'session_start_time' format. "
                                        "Please fill in correct format.")
            return None, error
        if self.form_experimenter.text() != '':
            data['experimenter'] = self.form_experimenter.text()
        else:
            data['experimenter'] = None
        if self.form_experiment_description.text() != '':
            data['experiment_description'] = self.form_experiment_description.text()
        else:
            data['experiment_description'] = None
        if self.form_session_id.text() != '':
            data['session_id'] = self.form_session_id.text()
        else:
            data['session_id'] = None
        if self.form_institution.text() != '':
            data['institution'] = self.form_institution.text()
        else:
            data['institution'] = None
        if self.form_lab.text() != '':
            data['lab'] = self.form_lab.text()
        else:
            data['lab'] = None
        if 'lab_meta_data' in self.metadata.keys():
            data['lab_meta_data'], error = self.lab_meta_data.read_fields()
        if len(self.form_keywords.text()) > 0:
            keywords = self.form_keywords.text()
            data['keywords'] = [kw.strip() for kw in keywords.split(',')]
        else:
            data['keywords'] = None
        if self.form_notes.text() != '':
            data['notes'] = self.form_notes.text()
        else:
            data['notes'] = None
        if self.form_pharmacology.text() != '':
            data['pharmacology'] = self.form_pharmacology.text()
        else:
            data['pharmacology'] = None
        if self.form_protocol.text() != '':
            data['protocol'] = self.form_protocol.text()
        else:
            data['protocol'] = None
        if self.form_related_publications.text() != '':
            data['related_publications'] = self.form_related_publications.text()
        else:
            data['related_publications'] = None
        if self.form_slices.text() != '':
            data['slices'] = self.form_slices.text()
        else:
            data['slices'] = None
        if self.form_data_collection.text() != '':
            data['data_collection'] = self.form_data_collection.text()
        else:
            data['data_collection'] = None
        if self.form_surgery.text() != '':
            data['surgery'] = self.form_surgery.text()
        else:
            data['surgery'] = None
        if self.form_virus.text() != '':
            data['virus'] = self.form_virus.text()
        else:
            data['virus'] = None
        if self.form_stimulus_notes.text() != '':
            data['stimulus_notes'] = self.form_stimulus_notes.text()
        else:
            data['stimulus_notes'] = None
        return data, error

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_session_description.setText(data['session_description'])
        self.form_identifier.setText(data['identifier'])
        if 'session_start_time' in data and data['session_start_time']:
            str_datetime = data['session_start_time'].strftime('%d/%m/%Y, %H:%M')
            self.form_session_start_time1.setText(str_datetime.split(',')[0])
            self.form_session_start_time2.setText(str_datetime.split(',')[1].strip())
        if 'experimenter' in data and data['experimenter'] is not None:
            if isinstance(data['experimenter'],list):
                self.form_experimenter.setText(','.join(str(x) for x in data['experimenter']))
            else:
                self.form_experimenter.setText(data['experimenter'])
        if 'experiment_description' in data:
            self.form_experiment_description.setText(data['experiment_description'])
        if 'session_id' in data:
            self.form_session_id.setText(data['session_id'])
        if 'institution' in data:
            self.form_institution.setText(data['institution'])
        if 'lab' in data:
            self.form_lab.setText(data['lab'])
        if 'keywords' in data and data['keywords'] is not None:
            self.form_keywords.setText(','.join(str(x) for x in data['keywords']))
        if 'notes' in data:
            self.form_notes.setText(data['notes'])
        if 'pharmacology' in data:
            self.form_pharmacology.setText(data['pharmacology'])
        if 'protocol' in data:
            self.form_protocol.setText(data['protocol'])
        if 'related_publications' in data:
            self.form_related_publications.setText(data['related_publications'])
        if 'slices' in data:
            self.form_slices.setText(data['slices'])
        if 'data_collection' in data:
            self.form_data_collection.setText(data['data_collection'])
        if 'surgery' in data:
            self.form_surgery.setText(data['surgery'])
        if 'virus' in data:
            self.form_virus.setText(data['virus'])
        if 'stimulus_notes' in data:
            self.form_stimulus_notes.setText(data['stimulus_notes'])


#class GroupSubject(QGroupBox):
class GroupSubject(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for 'pynwb.file.Subject' fields filling form."""
        super().__init__(title="Subject", parent=parent)
        #self.setTitle('Subject')
        self.group_type = 'Subject'

        self.lbl_age = QLabel('age:')
        self.form_age = QLineEdit('')
        self.form_age.setPlaceholderText("age")
        self.form_age.setToolTip("the age of the subject")

        self.lbl_description = QLabel('description:')
        self.form_description = QLineEdit('')
        self.form_description.setPlaceholderText("description")
        self.form_description.setToolTip("a description of the subject")

        self.lbl_genotype = QLabel('genotype:')
        self.form_genotype = QLineEdit('')
        self.form_genotype.setPlaceholderText("genotype")
        self.form_genotype.setToolTip("the genotype of the subject")

        self.lbl_sex = QLabel('sex:')
        self.form_sex = QLineEdit('')
        self.form_sex.setPlaceholderText("sex")
        self.form_sex.setToolTip("the sex of the subject")

        self.lbl_species = QLabel('species:')
        self.form_species = QLineEdit('')
        self.form_species.setPlaceholderText("species")
        self.form_species.setToolTip("the species of the subject")

        self.lbl_subject_id = QLabel('subject_id:')
        self.form_subject_id = QLineEdit('')
        self.form_subject_id.setPlaceholderText("subject_id")
        self.form_subject_id.setToolTip("a unique identifier for the subject")

        self.lbl_weight = QLabel('weight:')
        self.form_weight = QLineEdit('')
        self.form_weight.setPlaceholderText("weight")
        self.form_weight.setToolTip("the weight of the subject")

        self.lbl_date_of_birth = QLabel('date_of_birth:')
        self.form_date_of_birth = QLineEdit('')
        self.form_date_of_birth.setPlaceholderText(datetime.now().strftime("%d/%m/%Y"))
        self.form_date_of_birth.setToolTip(
            "datetime of date of birth. May be supplied instead of age.")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_age, 0, 0, 1, 2)
        self.grid.addWidget(self.form_age, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_description, 1, 0, 1, 2)
        self.grid.addWidget(self.form_description, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_genotype, 2, 0, 1, 2)
        self.grid.addWidget(self.form_genotype, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_sex, 3, 0, 1, 2)
        self.grid.addWidget(self.form_sex, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_species, 4, 0, 1, 2)
        self.grid.addWidget(self.form_species, 4, 2, 1, 4)
        self.grid.addWidget(self.lbl_subject_id, 5, 0, 1, 2)
        self.grid.addWidget(self.form_subject_id, 5, 2, 1, 4)
        self.grid.addWidget(self.lbl_weight, 6, 0, 1, 2)
        self.grid.addWidget(self.form_weight, 6, 2, 1, 4)
        self.grid.addWidget(self.lbl_date_of_birth, 7, 0, 1, 2)
        self.grid.addWidget(self.form_date_of_birth, 7, 2, 1, 4)

        #self.setLayout(self.grid)
        self.setContentLayout(self.grid)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        error = None
        data = {}
        data['age'] = self.form_age.text()
        data['description'] = self.form_description.text()
        data['genotype'] = self.form_genotype.text()
        data['sex'] = self.form_sex.text()
        data['species'] = self.form_species.text()
        data['subject_id'] = self.form_subject_id.text()
        data['weight'] = self.form_weight.text()
        str_datetime = self.form_date_of_birth.text()
        if len(str_datetime) > 0:
            data['date_of_birth'] = datetime.strptime(str_datetime, '%d/%m/%Y')
        else:
            data['date_of_birth'] = ''
        return data, error

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        if 'age' in data:
            self.form_age.setText(data['age'])
        if 'description' in data:
            self.form_description.setText(data['description'])
        if 'genotype' in data:
            self.form_genotype.setText(data['genotype'])
        if 'sex' in data:
            self.form_sex.setText(data['sex'])
        if 'species' in data:
            self.form_species.setText(data['species'])
        if 'subject_id' in data:
            self.form_subject_id.setText(data['subject_id'])
        if 'weight' in data:
            self.form_weight.setText(data['weight'])
        if 'date_of_birth' in data:
            self.form_date_of_birth.setText(data['date_of_birth'].strftime("%d/%m/%Y"))


class GroupDevice(CollapsibleBox):
    def __init__(self, parent):
        """Groupbox for pynwb.device.Device fields filling form."""
        super().__init__(title='Device', parent=parent)
        self.parent = parent
        self.pynwb_class = pynwb.device.Device
        self.group_type = 'Device'

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit('Device')
        self.form_name.setToolTip("the name pof this device")

        self.grid = QGridLayout()
        self.grid.setColumnStretch(2, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        #self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        return data

    def write_fields(self, metadata={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(str(metadata['name']))
        self.setContentLayout(self.grid)


class GroupCustomExtension(QGroupBox):
    def __init__(self, parent, metadata):
        """Groupbox for custom extension fields filling form."""
        super().__init__()
        self.setTitle(metadata['neurodata_type'])
        self.parent = parent
        self.metadata = metadata
        self.group_type = metadata['neurodata_type']

        self.lbl_name = QLabel('name<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_name = QLineEdit(metadata['name'])
        self.form_name.setToolTip("The unique name of this " + metadata['neurodata_type'] + " group.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  metadata['neurodata_type']):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText(metadata['name']+str(nInstances))

        self.grid = QGridLayout()
        self.grid.setColumnStretch(3, 1)
        self.grid.setColumnStretch(5, 1)
        self.grid.addWidget(self.lbl_name, 0, 0, 1, 2)
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)

        # Dynamically created custom fields
        self.intValidator = QIntValidator(self)
        self.floatValidator = QDoubleValidator(self)
        keys_list = list(metadata.keys())
        keys_list.remove('name')
        keys_list.remove('neurodata_type')
        for ii, key in enumerate(keys_list):
            val = metadata[key]
            lbl_key = QLabel(key+':')
            setattr(self, 'lbl_'+key, lbl_key)
            if isinstance(val, bool):
                chk_val = QLineEdit(str(val))
                chk_val = QCheckBox("True")
                chk_val.setChecked(val)
                setattr(self, 'form_'+key, chk_val)
                self.grid.addWidget(lbl_key, ii+1, 0, 1, 2)
                self.grid.addWidget(chk_val, ii+1, 2, 1, 2)
            elif isinstance(val, (int, np.int)):
                form_val = QLineEdit(str(val))
                form_val.setValidator(self.intValidator)
                setattr(self, 'form_'+key, form_val)
                self.grid.addWidget(lbl_key, ii+1, 0, 1, 2)
                self.grid.addWidget(form_val, ii+1, 2, 1, 4)
            elif isinstance(val, (float, np.float)):
                form_val = QLineEdit(str(val))
                form_val.setValidator(self.floatValidator)
                setattr(self, 'form_'+key, form_val)
                self.grid.addWidget(lbl_key, ii+1, 0, 1, 2)
                self.grid.addWidget(form_val, ii+1, 2, 1, 4)
            elif isinstance(val, str):
                form_val = QLineEdit(str(val))
                setattr(self, 'form_'+key, form_val)
                self.grid.addWidget(lbl_key, ii+1, 0, 1, 2)
                self.grid.addWidget(form_val, ii+1, 2, 1, 4)
            elif isinstance(val, datetime):
                pass
                # form_date = QLineEdit(val.strftime("%d/%m/%Y"))
                # form_date.setToolTip("dd/mm/yyyy")
                # setattr(self, 'form_date_'+str(ii), form_date)
                # form_time = QLineEdit(val.strftime("%H:%M"))
                # form_time.setToolTip("dd/mm/yyyy")
                # setattr(self, 'form_time_'+str(ii), form_time)
                # self.grid.addWidget(lbl_key, ii+1, 0, 1, 2)
                # self.grid.addWidget(form_date, ii+1, 2, 1, 2)
                # self.grid.addWidget(form_time, ii+1, 4, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        pass

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        error = None
        keys_list = list(self.metadata.keys())
        keys_list.remove('neurodata_type')
        for ii, key in enumerate(keys_list):
            attr = getattr(self, 'form_'+key)
            if isinstance(self.metadata[key], bool):
                self.metadata[key] = attr.text() == True
            elif isinstance(self.metadata[key], (int, np.int)):
                self.metadata[key] = int(attr.text())
            elif isinstance(self.metadata[key], (float, np.float)):
                self.metadata[key] = float(attr.text())
            elif isinstance(self.metadata[key], str):
                self.metadata[key] = attr.text()
        return self.metadata, error

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        pass


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
        self.form_name = QLineEdit('CustomName')
        self.form_name.setToolTip("The unique name of this group.")
        nInstances = 0
        for grp in self.parent.groups_list:
            if isinstance(grp,  GroupCustomExample):
                nInstances += 1
        if nInstances > 0:
            self.form_name.setText('CustomName'+str(nInstances))

        # Mandatory field: we fill it with default values
        self.lbl_mandatory = QLabel('mandatory<span style="color:'+required_asterisk_color+';">*</span>:')
        self.form_mandatory = QLineEdit('ABC123')
        self.form_mandatory.setToolTip("This is a mandatory field.")

        # Optional field: we leave a placeholder text as example
        self.lbl_optional = QLabel('optional:')
        self.form_optional = QLineEdit('')
        self.form_optional.setPlaceholderText("example")
        self.form_optional.setToolTip("This is an optional field.")

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
        self.grid.addWidget(self.form_name, 0, 2, 1, 4)
        self.grid.addWidget(self.lbl_mandatory, 1, 0, 1, 2)
        self.grid.addWidget(self.form_mandatory, 1, 2, 1, 4)
        self.grid.addWidget(self.lbl_optional, 2, 0, 1, 2)
        self.grid.addWidget(self.form_optional, 2, 2, 1, 4)
        self.grid.addWidget(self.lbl_link, 3, 0, 1, 2)
        self.grid.addWidget(self.combo_link, 3, 2, 1, 4)
        self.grid.addWidget(self.lbl_script, 4, 0, 1, 2)
        self.grid.addWidget(self.chk_script, 4, 2, 1, 2)
        self.setLayout(self.grid)

    def refresh_objects_references(self, metadata=None):
        """Refreshes references with existing objects in parent group."""
        self.combo_link.clear()
        for grp in self.parent.groups_list:
            if isinstance(grp, GroupCustomExample):
                self.combo_link.addItem(grp.form_name.text())

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        data = {}
        data['name'] = self.form_name.text()
        data['mandatory'] = self.form_mandatory.text()
        data['optional'] = self.form_optional.text()
        data['link'] = self.combo_link.currentText()
        if self.chk_script.isChecked():
            data['script'] = True
        return data

    def write_fields(self, data={}):
        """Reads structured dictionary and write in form fields."""
        self.form_name.setText(data['name'])
        self.form_mandatory.setText(data['mandatory'])
        if 'optional' in data:
            self.form_optional.setText(data['optional'])
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
