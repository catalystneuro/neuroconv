from PySide2.QtWidgets import QVBoxLayout, QGridLayout, QGroupBox, QComboBox
from nwbn_conversion_tools.gui.classes.forms_basic import BasicFormCollapsible
import pynwb
from itertools import groupby


class GroupOptogeneticStimulusSite(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.ogen.OptogeneticStimulusSite fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.ogen.OptogeneticStimulusSite, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'device',
             'type': 'link',
             'class': 'Device',
             'required': True,
             'doc': 'The device that was used to record'},
        ]
        self.fields_info.extend(specific_fields)


class GroupOptogeneticSeries(BasicFormCollapsible):
    def __init__(self, parent, metadata=None):
        """Groupbox for pynwb.ogen.OptogeneticSeries fields filling form."""
        super().__init__(parent=parent, pynwb_class=pynwb.ogen.OptogeneticSeries, metadata=metadata)

    def fields_info_update(self):
        """Updates fields info with specific fields from the inheriting class."""
        specific_fields = [
            {'name': 'site',
             'type': 'link',
             'class': 'OptogeneticStimulusSite',
             'required': True,
             'doc': 'The site to which this stimulus was applied.'},
        ]
        self.fields_info.extend(specific_fields)


class GroupOgen(QGroupBox):
    def __init__(self, parent):
        """Groupbox for Ogen module fields filling form."""
        super().__init__()
        self.setTitle('Ogen')
        self.group_type = 'Ogen'
        self.groups_list = []

        self.vbox1 = QVBoxLayout()
        self.vbox1.addStretch()

        self.grid = QGridLayout()
        self.grid.setColumnStretch(5, 1)
        self.grid.addLayout(self.vbox1, 2, 0, 1, 6)
        self.setLayout(self.grid)

    def add_group(self, group, metadata=None):
        """Adds group form."""
        if metadata is not None:
            group.write_fields(metadata=metadata)
        group.form_name.textChanged.connect(self.refresh_children)
        self.groups_list.append(group)
        nWidgetsVbox = self.vbox1.count()
        self.vbox1.insertWidget(nWidgetsVbox - 1, group)  # insert before the stretch
        self.refresh_children(metadata=metadata)

    def is_referenced(self, grp_unique_name):
        """Tests if a group is being referenced any other groups. Returns boolean."""
        nWidgetsVbox = self.vbox1.count()
        for i in range(nWidgetsVbox):
            if self.vbox1.itemAt(i).widget() is not None:
                other_grp = self.vbox1.itemAt(i).widget()
                # check if this subgroup has any ComboBox referencing grp_unique_name
                for ch in other_grp.children():
                    if isinstance(ch, (CustomComboBox, QComboBox)):
                        if ch.currentText() == grp_unique_name:
                            return True
        return False

    def refresh_children(self, metadata=None):
        """Refreshes references with existing objects in child groups."""
        for child in self.groups_list:
            child.refresh_objects_references(metadata=metadata)

    def read_fields(self):
        """Reads fields and returns them structured in a dictionary."""
        error = None
        data = {}
        # group_type counts, if there are multiple groups of same type, they are saved in a list
        grp_types = [grp.group_type for grp in self.groups_list]
        grp_type_count = {value: len(list(freq)) for value, freq in groupby(sorted(grp_types))}
        # initiate lists as values for groups keys with count > 1
        for k, v in grp_type_count.items():
            if v > 1 or k == 'Device' or k == 'OptogeneticStimulusSite' or k == 'OptogeneticSeries':
                data[k] = []
        # iterate over existing groups and copy their metadata
        for grp in self.groups_list:
            if grp_type_count[grp.group_type] > 1 or grp.group_type == 'Device' \
               or grp.group_type == 'OptogeneticStimulusSite' \
               or grp.group_type == 'OptogeneticSeries':
                data[grp.group_type].append(grp.read_fields())
            else:
                data[grp.group_type] = grp.read_fields()
        return data, error


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()
