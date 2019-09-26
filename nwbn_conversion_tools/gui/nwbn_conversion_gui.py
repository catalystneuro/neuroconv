from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
                             QPushButton, QLineEdit, QTextEdit, QVBoxLayout,
                             QGridLayout, QSplitter, QLabel, QFileDialog,
                             QMessageBox, QComboBox, QScrollArea, QStyle)
from nwbn_conversion_tools.gui.classes.forms_general import GroupNwbfile
from nwbn_conversion_tools.gui.classes.forms_ophys import GroupOphys
from nwbn_conversion_tools.gui.classes.forms_ephys import GroupEphys
from nwbn_conversion_tools.gui.classes.forms_behavior import GroupBehavior
import datetime
import importlib
import yaml
import os
import sys


class Application(QMainWindow):
    def __init__(self, metafile=None, conversion_module='', show_add_del=False):
        super().__init__()
        self.source_files_path = os.getcwd()
        self.f_source = ''
        self.conversion_module_path = conversion_module
        self.show_add_del = show_add_del

        self.centralwidget = QWidget()
        self.setCentralWidget(self.centralwidget)
        self.resize(1200, 900)
        self.setWindowTitle('NWB:N conversion tools')

        # Initialize GUI elements
        self.init_gui()
        self.load_meta_file(filename=metafile)
        self.show()

    def init_gui(self):
        """Initiates GUI elements."""
        mainMenu = self.menuBar()

        fileMenu = mainMenu.addMenu('File')
        action_choose_conversion = QAction('Choose conversion module', self)
        fileMenu.addAction(action_choose_conversion)
        action_choose_conversion.triggered.connect(self.load_conversion_module)

        helpMenu = mainMenu.addMenu('Help')
        action_about = QAction('About', self)
        helpMenu.addAction(action_about)
        action_about.triggered.connect(self.about)

        # Center panels -------------------------------------------------------
        self.groups_list = []

        # Left-side panel: forms
        btn_save_meta = QPushButton('Save metafile')
        btn_save_meta.clicked.connect(self.save_meta_file)
        btn_run_conversion = QPushButton('Run conversion')
        btn_run_conversion.clicked.connect(self.run_conversion)
        btn_form_editor = QPushButton('Form -> Editor')
        btn_form_editor.clicked.connect(self.form_to_editor)

        self.lbl_meta_file = QLabel('meta file:')
        self.lin_meta_file = QLineEdit('')
        self.btn_meta_file = QPushButton()
        self.btn_meta_file.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_meta_file.clicked.connect(lambda: self.load_meta_file(filename=None))
        self.lbl_source_file = QLabel('source files:')
        self.lin_source_file = QLineEdit('')
        self.btn_source_file = QPushButton()
        self.btn_source_file.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_source_file.clicked.connect(self.load_source_files)
        self.lbl_nwb_file = QLabel('nwb file:')
        self.lin_nwb_file = QLineEdit('')
        self.btn_nwb_file = QPushButton()
        self.btn_nwb_file.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_nwb_file.clicked.connect(self.load_nwb_file)

        l_grid1 = QGridLayout()
        l_grid1.setColumnStretch(3, 1)
        l_grid1.addWidget(btn_save_meta, 0, 0, 1, 1)
        l_grid1.addWidget(btn_run_conversion, 0, 1, 1, 1)
        l_grid1.addWidget(QLabel(), 0, 2, 1, 2)
        l_grid1.addWidget(btn_form_editor, 0, 4, 1, 2)
        l_grid1.addWidget(self.lbl_meta_file, 1, 0, 1, 2)
        l_grid1.addWidget(self.lin_meta_file, 1, 2, 1, 3)
        l_grid1.addWidget(self.btn_meta_file, 1, 5, 1, 1)
        l_grid1.addWidget(self.lbl_source_file, 2, 0, 1, 2)
        l_grid1.addWidget(self.lin_source_file, 2, 2, 1, 3)
        l_grid1.addWidget(self.btn_source_file, 2, 5, 1, 1)
        l_grid1.addWidget(self.lbl_nwb_file, 3, 0, 1, 2)
        l_grid1.addWidget(self.lin_nwb_file, 3, 2, 1, 3)
        l_grid1.addWidget(self.btn_nwb_file, 3, 5, 1, 1)

        self.l_vbox1 = QVBoxLayout()
        self.l_vbox1.addStretch()
        scroll_aux = QWidget()
        scroll_aux.setLayout(self.l_vbox1)
        l_scroll = QScrollArea()
        l_scroll.setWidget(scroll_aux)
        l_scroll.setWidgetResizable(True)

        self.l_vbox2 = QVBoxLayout()
        self.l_vbox2.addLayout(l_grid1)
        self.l_vbox2.addWidget(l_scroll)

        # Right-side panel
        # Metadata text
        editor_label = QLabel('Metafile preview:')
        r_grid1 = QGridLayout()
        r_grid1.setColumnStretch(1, 1)
        r_grid1.addWidget(editor_label, 0, 0, 1, 1)
        r_grid1.addWidget(QLabel(), 0, 1, 1, 1)
        self.editor = QTextEdit()
        r_vbox1 = QVBoxLayout()
        r_vbox1.addLayout(r_grid1)
        r_vbox1.addWidget(self.editor)

        # Logger
        log_label = QLabel('Log:')
        r_grid2 = QGridLayout()
        r_grid2.setColumnStretch(1, 1)
        r_grid2.addWidget(log_label, 0, 0, 1, 1)
        r_grid2.addWidget(QLabel(), 0, 1, 1, 1)
        self.logger = QTextEdit()
        self.logger.setReadOnly(True)
        r_vbox2 = QVBoxLayout()
        r_vbox2.addLayout(r_grid2)
        r_vbox2.addWidget(self.logger)

        r_vsplitter = QSplitter(Qt.Vertical)
        ru_w = QWidget()
        ru_w.setLayout(r_vbox1)
        rb_w = QWidget()
        rb_w.setLayout(r_vbox2)
        r_vsplitter.addWidget(ru_w)
        r_vsplitter.addWidget(rb_w)

        # Main Layout
        self.left_w = QWidget()
        self.left_w.setLayout(self.l_vbox2)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.left_w)
        self.splitter.addWidget(r_vsplitter)

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.splitter)
        self.centralwidget.setLayout(self.main_layout)

        # Background color
        p = self.palette()
        p.setColor(self.backgroundRole(), QtCore.Qt.white)
        self.setPalette(p)

    def write_to_logger(self, txt):
        time = datetime.datetime.now().time().strftime("%H:%M:%S")
        full_txt = "[" + time + "]    " + txt
        self.logger.append(full_txt)

    def run_conversion(self):
        """Runs conversion function."""
        self.write_to_logger('Converting data to NWB... please wait.')
        self.toggle_enable_gui(enable=False)
        self.thread = ConversionFunctionThread(self)
        self.thread.finished.connect(lambda: self.finish_conversion(error=self.thread.error))
        self.thread.start()

    def finish_conversion(self, error):
        if error:
            self.write_to_logger('ERROR:')
            self.write_to_logger(str(error))
        else:
            self.write_to_logger('Data successfully converted to NWB.')
        self.toggle_enable_gui(enable=True)

    def toggle_enable_gui(self, enable):
        self.editor.setEnabled(enable)
        self.left_w.setEnabled(enable)

    def save_meta_file(self):
        """Saves metadata to .yml file."""
        filename, _ = QFileDialog.getSaveFileName(self, 'Save file', '', "(*.yml)")
        if filename:
            data = {}
            for grp in self.groups_list:
                info, error = grp.read_fields()
                if error is None:
                    data[grp.group_type] = info
                else:
                    return
            with open(filename, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)

    def form_to_editor(self):
        """Loads data from form to editor."""
        data = {}
        for grp in self.groups_list:
            info, error = grp.read_fields()
            print(grp, error)
            if error is None:
                data[grp.group_type] = info
            else:
                return
        txt = yaml.dump(data, default_flow_style=False)
        self.editor.setText(txt)

    def load_source_files(self):
        """Browser to source files location."""
        filenames, ftype = QFileDialog.getOpenFileNames(self, 'Open file', '', "(*)")
        if len(filenames):
            all_names = ''
            for fname in filenames:
                all_names += os.path.split(fname)[1]+', '
            self.lin_source_file.setText(all_names[:-3])
            self.source_files_path = os.path.split(fname)[0]
            self.f_source = filenames

    def load_meta_file(self, filename=None):
        '''Browser to .yml file containing metadata for NWB.'''
        if filename is None:
            filename, ftype = QFileDialog.getOpenFileName(self, 'Open file',
                                                          self.source_files_path, "(*.yml)")
            if ftype != '(*.yml)':
                return
        self.lin_meta_file.setText(filename)
        with open(filename) as f:
            self.metadata = yaml.safe_load(f)
        txt = yaml.dump(self.metadata, default_flow_style=False)
        self.editor.setText(txt)
        self.update_forms()

    def load_conversion_module(self):
        """Browser to conversion script file location."""
        filename, ftype = QFileDialog.getOpenFileName(self, 'Open file',
                                                      self.source_files_path, "(*py)")
        if filename is not None:
            self.conversion_module_path = filename

    def load_nwb_file(self):
        """Browser to source file location."""
        filename, ftype = QFileDialog.getSaveFileName(self, 'Save file',
                                                      self.source_files_path, "(*nwb)")
        if filename is not None:
            self.lin_nwb_file.setText(filename)

    def clean_groups(self):
        """Removes all groups widgets."""
        for grp in self.groups_list:
            nWidgetsVbox = self.l_vbox1.count()
            for i in range(nWidgetsVbox):
                if self.l_vbox1.itemAt(i) is not None:
                    if grp == self.l_vbox1.itemAt(i).widget():
                        self.l_vbox1.itemAt(i).widget().setParent(None)  # deletes widget
        self.groups_list = []                        # deletes all list items

    def update_forms(self):
        """Updates forms fields with values in metadata."""
        self.clean_groups()
        for grp in self.metadata:
            if grp == 'NWBFile':
                item = GroupNwbfile(self)
                item.write_fields(data=self.metadata['NWBFile'])
                self.groups_list.append(item)
                self.l_vbox1.addWidget(item)
            if grp == 'Ophys':
                item = GroupOphys(self)
                for subgroup in self.metadata[grp]:
                    # if many items of same class, in list
                    if isinstance(self.metadata[grp][subgroup], list):
                        for subsub in self.metadata[grp][subgroup]:
                            item.add_group(group_type=subgroup,
                                           write_data=subsub)
                    else:  # if it's just one item of this class
                        item.add_group(group_type=subgroup,
                                       write_data=self.metadata[grp][subgroup])
                self.groups_list.append(item)
                self.l_vbox1.addWidget(item)
            if grp == 'Ephys':
                item = GroupEphys(self)
                for subgroup in self.metadata[grp]:
                    # if many items of same class, in list
                    if isinstance(self.metadata[grp][subgroup], list):
                        for subsub in self.metadata[grp][subgroup]:
                            item.add_group(group_type=subgroup,
                                           write_data=subsub)
                    else:  # if it's just one item of this class
                        item.add_group(group_type=subgroup,
                                       write_data=self.metadata[grp][subgroup])
                self.groups_list.append(item)
                self.l_vbox1.addWidget(item)
            if grp == 'Behavior':
                item = GroupBehavior(self)
                for subgroup in self.metadata[grp]:
                    # if many items of same class, in list
                    if isinstance(self.metadata[grp][subgroup], list):
                        for subsub in self.metadata[grp][subgroup]:
                            item.add_group(group_type=subgroup,
                                           write_data=subsub)
                    else:  # if it's just one item of this class
                        item.add_group(group_type=subgroup,
                                       write_data=self.metadata[grp][subgroup])
                self.groups_list.append(item)
                self.l_vbox1.addWidget(item)

    def about(self):
        """About dialog."""
        msg = QMessageBox()
        msg.setWindowTitle("About NWB conversion")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Version: 1.0.0 \n"
                    "Shared tools for converting data from various formats to NWB:N 2.0.\n ")
        msg.setInformativeText("<a href='https://github.com/NeurodataWithoutBorders/nwbn-conversion-tools'>NWB conversion tools Github page</a>")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def closeEvent(self, event):
        """Before exiting, executes these actions."""
        event.accept()


# Runs conversion function, useful to wait for thread
class ConversionFunctionThread(QtCore.QThread):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.error = None

    def run(self):
        try:
            mod_file = self.parent.conversion_module_path
            spec = importlib.util.spec_from_file_location(os.path.basename(mod_file).strip('.py'), mod_file)
            conv_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(conv_module)
            f_sources = tuple(self.parent.f_source)    # multiple source files
            conv_module.conversion_function(*f_sources,
                                            f_nwb=self.parent.lin_nwb_file.text(),
                                            metafile=self.parent.lin_meta_file.text())
            self.error = None
        except Exception as error:
            self.error = error


class CustomComboBox(QComboBox):
    def __init__(self):
        """Class created to ignore mouse wheel events on combobox."""
        super().__init__()

    def wheelEvent(self, event):
        event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)  # instantiate a QtGui (holder for the app)
    ex = Application()
    sys.exit(app.exec_())


# If it is imported as a module
def nwbn_conversion_gui(metafile=None, conversion_module='', show_add_del=False):
    """Sets up QT application."""
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)  # instantiate a QtGui (holder for the app)
    ex = Application(metafile=metafile,
                     conversion_module=conversion_module,
                     show_add_del=show_add_del)
    sys.exit(app.exec_())
