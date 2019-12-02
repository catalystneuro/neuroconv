from PySide2 import QtCore
from PySide2.QtCore import Qt
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2.QtWidgets import (QMainWindow, QWidget, QApplication, QAction,
                             QPushButton, QLineEdit, QTextEdit, QVBoxLayout,
                             QGridLayout, QSplitter, QLabel, QFileDialog,
                             QMessageBox, QComboBox, QScrollArea, QStyle,
                             QGroupBox, QCheckBox, QTabWidget)

from nwbn_conversion_tools.gui.classes.forms_general import GroupNwbfile, GroupSubject
from nwbn_conversion_tools.gui.classes.forms_ophys import GroupOphys
from nwbn_conversion_tools.gui.classes.forms_ecephys import GroupEcephys
from nwbn_conversion_tools.gui.classes.forms_behavior import GroupBehavior

import numpy as np
import nbformat as nbf
from pathlib import Path
import tempfile
import socket
import psutil
import shutil
import datetime
import importlib
import yaml
import sys
import os


class Application(QMainWindow):
    def __init__(self, metafile=None, conversion_module='', source_paths={},
                 kwargs_fields={}, show_add_del=False):
        super().__init__()
        # Dictionary storing source files paths
        self.source_paths = source_paths
        # Path to conversion module .py file
        self.conversion_module_path = conversion_module
        # Dictionary storing custom boolean options (to form checkboxes)
        self.kwargs_fields = kwargs_fields
        # Boolean control to either show/hide the option for add/del Groups
        self.show_add_del = show_add_del
        # Temporary folder path
        self.temp_dir = tempfile.mkdtemp()

        self.resize(1200, 900)
        self.setWindowTitle('NWB:N conversion tools')

        # Initialize GUI elements
        self.init_gui()
        self.init_meta_tab()
        self.load_meta_file(filename=metafile)
        self.init_nwb_explorer()
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

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

    def init_meta_tab(self):
        # Center panels -------------------------------------------------------
        self.groups_list = []

        # Left-side panel: forms
        self.btn_load_meta = QPushButton('Load metafile')
        self.btn_load_meta.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.btn_load_meta.clicked.connect(lambda: self.load_meta_file(filename=None))
        self.btn_load_meta.setToolTip("The YAML file with metadata for this conversion.\n"
                                      "You can customize the metadata in the forms below.")
        self.btn_save_meta = QPushButton('Save metafile')
        self.btn_save_meta.setIcon(self.style().standardIcon(QStyle.SP_DriveFDIcon))
        self.btn_save_meta.clicked.connect(self.save_meta_file)
        self.btn_run_conversion = QPushButton('Run conversion')
        self.btn_run_conversion.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_run_conversion.clicked.connect(self.run_conversion)
        self.btn_form_editor = QPushButton('Form -> Editor')
        self.btn_form_editor.clicked.connect(self.form_to_editor)

        self.lbl_nwb_file = QLabel('Output nwb file:')
        self.lbl_nwb_file.setToolTip("Path to the NWB file that will be created.")
        self.lin_nwb_file = QLineEdit('')
        self.btn_nwb_file = QPushButton()
        self.btn_nwb_file.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_nwb_file.clicked.connect(self.load_nwb_file)

        l_grid1 = QGridLayout()
        l_grid1.setColumnStretch(3, 1)
        l_grid1.addWidget(self.btn_load_meta, 0, 0, 1, 1)
        l_grid1.addWidget(self.btn_save_meta, 0, 1, 1, 1)
        l_grid1.addWidget(self.btn_run_conversion, 0, 2, 1, 1)
        l_grid1.addWidget(QLabel(), 0, 3, 1, 1)
        l_grid1.addWidget(self.btn_form_editor, 0, 4, 1, 2)
        l_grid1.addWidget(self.lbl_nwb_file, 1, 0, 1, 1)
        l_grid1.addWidget(self.lin_nwb_file, 1, 1, 1, 3)
        l_grid1.addWidget(self.btn_nwb_file, 1, 4, 1, 1)

        # Adds custom files/dir paths fields
        if len(self.source_paths.keys()) == 0:
            self.lbl_source_file = QLabel('source files:')
            self.lin_source_file = QLineEdit('')
            self.btn_source_file = QPushButton()
            self.btn_source_file.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
            self.btn_source_file.clicked.connect(self.load_source_files)
            l_grid1.addWidget(self.lbl_source_file, 3, 0, 1, 1)
            l_grid1.addWidget(self.lin_source_file, 3, 1, 1, 3)
            l_grid1.addWidget(self.btn_source_file, 3, 4, 1, 1)
        else:
            self.group_source_paths = QGroupBox('Source paths')
            self.grid_source = QGridLayout()
            self.grid_source.setColumnStretch(3, 1)
            ii = -1
            for k, v in self.source_paths.items():
                ii += 1
                lbl_src = QLabel(k+':')
                setattr(self, 'lbl_src_'+str(ii), lbl_src)
                lin_src = QLineEdit('')
                setattr(self, 'lin_src_'+str(ii), lin_src)
                btn_src = QPushButton()
                btn_src.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
                setattr(self, 'btn_src_'+str(ii), btn_src)
                if v['type'] == 'file':
                    btn_src.clicked.connect((lambda x: lambda: self.load_source_files(x[0], x[1]))([ii, k]))
                else:
                    btn_src.clicked.connect((lambda x: lambda: self.load_source_dir(x[0], x[1]))([ii, k]))
                self.grid_source.addWidget(lbl_src, ii, 0, 1, 1)
                self.grid_source.addWidget(lin_src, ii, 1, 1, 3)
                self.grid_source.addWidget(btn_src, ii, 4, 1, 1)
            self.group_source_paths.setLayout(self.grid_source)
            l_grid1.addWidget(self.group_source_paths, 3, 0, 1, 6)

        # Adds custom kwargs checkboxes
        if len(self.kwargs_fields.keys()) > 0:
            self.group_kwargs = QGroupBox('KWARGS')
            self.grid_kwargs = QGridLayout()
            self.grid_kwargs.setColumnStretch(4, 1)
            ii = -1
            for k, v in self.kwargs_fields.items():
                ii += 1
                chk_kwargs = QCheckBox(k)
                chk_kwargs.setChecked(v)
                chk_kwargs.clicked.connect((lambda x: lambda: self.update_kwargs(x[0], x[1]))([ii, k]))
                setattr(self, 'chk_kwargs_'+str(ii), chk_kwargs)
                self.grid_kwargs.addWidget(chk_kwargs, ii//4, ii%4, 1, 1)
            self.group_kwargs.setLayout(self.grid_kwargs)
            l_grid1.addWidget(self.group_kwargs, 4, 0, 1, 6)

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

        r_vsplitter = QSplitter(QtCore.Qt.Vertical)
        ru_w = QWidget()
        ru_w.setLayout(r_vbox1)
        rb_w = QWidget()
        rb_w.setLayout(r_vbox2)
        r_vsplitter.addWidget(ru_w)
        r_vsplitter.addWidget(rb_w)

        # Metadata/conversion tab Layout
        self.left_w = QWidget()
        self.left_w.setLayout(self.l_vbox2)
        self.splitter = QSplitter(QtCore.Qt.Horizontal)
        self.splitter.addWidget(self.left_w)
        self.splitter.addWidget(r_vsplitter)

        self.metadata_layout = QVBoxLayout()
        self.metadata_layout.addWidget(self.splitter)
        self.tab_metadata = QWidget()
        self.tab_metadata.setLayout(self.metadata_layout)
        self.tabs.addTab(self.tab_metadata, 'Metadata/Conversion')

        # Background color
        p = self.palette()
        p.setColor(self.backgroundRole(), QtCore.Qt.white)
        self.setPalette(p)

    def init_nwb_explorer(self):
        """Initializes NWB file explorer tab"""
        self.tab_nwbexplorer = QWidget()
        self.btn_load_nwbexp = QPushButton('Load NWB')
        self.btn_load_nwbexp.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.btn_load_nwbexp.clicked.connect(self.load_nwb_explorer)
        self.btn_load_nwbexp.setToolTip("Choose NWB file to explore!")
        self.btn_close_nwbexp = QPushButton('Close')
        self.btn_close_nwbexp.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.btn_close_nwbexp.clicked.connect(self.close_nwb_explorer)
        self.btn_close_nwbexp.setToolTip("Close current file view.")
        self.html = QWebEngineView()

        # Layout
        self.grid_explorer = QGridLayout()
        self.grid_explorer.setColumnStretch(2, 1)
        self.grid_explorer.addWidget(self.btn_load_nwbexp, 0, 0, 1, 1)
        self.grid_explorer.addWidget(self.btn_close_nwbexp, 0, 1, 1, 1)
        self.grid_explorer.addWidget(QLabel(), 0, 2, 1, 1)
        self.vbox_explorer = QVBoxLayout()
        self.vbox_explorer.addLayout(self.grid_explorer)
        self.vbox_explorer.addWidget(self.html)
        self.tab_nwbexplorer.setLayout(self.vbox_explorer)

        # Add tab to GUI
        self.tabs.addTab(self.tab_nwbexplorer, 'NWB explorer')

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

    def read_metadata_from_form(self):
        """Loads metadata from form."""
        metadata = {}
        for grp in self.groups_list:
            info, error = grp.read_fields()
            if error is None:
                metadata[grp.group_type] = info
            else:
                return
        return metadata

    def form_to_editor(self):
        """Loads data from form to editor."""
        metadata = self.read_metadata_from_form()
        txt = yaml.dump(metadata, default_flow_style=False)
        self.editor.setText(txt)

    def update_kwargs(self, ind, key):
        """Updates the boolean values for keyword arguments."""
        chk_kw = getattr(self, 'chk_kwargs_'+str(ind))
        self.kwargs_fields[key] = chk_kw.isChecked()

    def load_source_files(self, ind, key):
        """Browser to source file location."""
        filenames, ftype = QFileDialog.getOpenFileNames(
            parent=self,
            caption='Open file',
            directory='',
            filter="(*)"
        )
        if len(filenames):
            all_names = ''
            for fname in filenames:
                all_names += fname + ', '
            lin_src = getattr(self, 'lin_src_'+str(ind))
            lin_src.setText(all_names[:-2])
            self.source_paths[key]['path'] = all_names[:-2]

    def load_source_dir(self, ind, key):
        """Browser to source directory location."""
        dirname = QFileDialog.getExistingDirectory(
            parent=self,
            caption='Source directory',
            directory=''
        )
        if len(dirname):
            lin_src = getattr(self, 'lin_src_'+str(ind))
            lin_src.setText(dirname)
            self.source_paths[key]['path'] = dirname

    def load_meta_file(self, filename=None):
        '''Browser to .yml file containing metadata for NWB.'''
        if filename is None:
            filename, ftype = QFileDialog.getOpenFileName(
                parent=self,
                caption='Open file',
                directory='',
                filter="(*.yml)"
            )
            if ftype != '(*.yml)':
                return
        with open(filename) as f:
            self.metadata = yaml.safe_load(f)
        txt = yaml.dump(self.metadata, default_flow_style=False)
        self.editor.setText(txt)
        self.update_forms()

    def load_conversion_module(self):
        """Browser to conversion script file location."""
        filename, ftype = QFileDialog.getOpenFileName(
            parent=self,
            caption='Open file',
            directory='',
            filter="(*py)"
        )
        if filename is not '':
            self.conversion_module_path = filename

    def load_nwb_file(self):
        """Browser to nwb file location."""
        filename, ftype = QFileDialog.getSaveFileName(
            parent=self,
            caption='Save file',
            directory='',
            filter="(*nwb)"
        )
        if filename is not None:
            self.lin_nwb_file.setText(filename)

    def load_nwb_explorer(self):
        """Browser to nwb file location."""
        filename, ftype = QFileDialog.getOpenFileName(
            parent=self,
            caption='Load file',
            directory='',
            filter="(*nwb)"
        )
        if filename is not '':
            self.run_voila(fname=filename)

    def close_nwb_explorer(self):
        """Close current NWB file view on explorer"""
        if hasattr(self, 'voilathread'):
            self.voilathread.stop()

    def run_voila(self, fname):
        """Set up notebook and run it with a dedicated Voila thread."""
        # Stop any current Voila thread
        self.close_nwb_explorer()
        # Write Figure + ipywidgets to a .ipynb file
        nb = nbf.v4.new_notebook()
        code = """
            from nwbwidgets import nwb2widget
            import pynwb
            import os

            fpath = os.path.join(r'""" + str(fname) + """')
            io = pynwb.NWBHDF5IO(fpath, 'r', load_namespaces=True)
            nwb = io.read()
            nwb2widget(nwb)
            #io.close()
            """
        nb['cells'] = [nbf.v4.new_code_cell(code)]
        nbpath = os.path.join(self.temp_dir, Path(fname).stem+'.ipynb')
        nbf.write(nb, nbpath)
        # Run instance of Voila with the just saved .ipynb file
        port = get_free_port()
        self.voilathread = voilaThread(parent=self, port=port, nbpath=nbpath)
        self.voilathread.start()
        # Load Voila instance on GUI
        self.update_html(url='http://localhost:'+str(port))
        #self.parent.write_to_logger(txt=self.name + " ready!")

    def update_html(self, url):
        """Loads temporary HTML file and render it."""
        self.html.load(QtCore.QUrl(url))
        self.html.show()

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
                item = GroupNwbfile(parent=self, metadata=self.metadata['NWBFile'])
                item.write_fields(data=self.metadata['NWBFile'])
                self.groups_list.append(item)
                self.l_vbox1.addWidget(item)
            if grp == 'Subject':
                item = GroupSubject(parent=self)
                item.write_fields(data=self.metadata['Subject'])
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
            if grp == 'Ecephys':
                item = GroupEcephys(self)
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
        nItems = self.l_vbox1.count()
        self.l_vbox1.addStretch(nItems)

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
        # Stop any current Voila thread
        self.close_nwb_explorer()
        # Remove any remaining temporary directory/files
        shutil.rmtree(self.temp_dir, ignore_errors=False, onerror=None)
        event.accept()


def get_free_port():
    not_free = True
    while not_free:
        port = np.random.randint(7000, 7999)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            res = sock.connect_ex(('localhost', port))
            if res != 0:
                not_free = False
    return port


def is_listening_to_port(process, port):
    is_listening = False
    # iterate over processe's children
    for child in process.children(recursive=True):
        # iterate over child connections
        for con in child.connections():
            if con.status=='LISTEN':
                if isinstance(con.laddr.port, int):
                    is_listening = con.laddr.port == port
                elif isinstance(con.laddr.port, list):
                    is_listening = port in con.laddr.port
                return is_listening
    return is_listening


class voilaThread(QtCore.QThread):
    def __init__(self, parent, port, nbpath):
        super().__init__()
        self.parent = parent
        self.port = port
        self.nbpath = nbpath

    def run(self):
        os.system("voila " + self.nbpath + " --no-browser --port "+str(self.port))

    def stop(self):
        pid = os.getpid()
        process = psutil.Process(pid)
        proc_list = []
        for child in process.children(recursive=True):
            is_listening = is_listening_to_port(child, self.port)
            if is_listening:
                proc_list.append(child)
        for proc in proc_list:
            for child in process.children(recursive=True):
                child.kill()


# Runs conversion function, useful to wait for thread
class ConversionFunctionThread(QtCore.QThread):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.error = None

    def run(self):
        #try:
        mod_file = self.parent.conversion_module_path
        spec = importlib.util.spec_from_file_location(os.path.basename(mod_file).strip('.py'), mod_file)
        conv_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conv_module)
        metadata = self.parent.read_metadata_from_form()
        conv_module.conversion_function(source_paths=self.parent.source_paths,
                                        f_nwb=self.parent.lin_nwb_file.text(),
                                        metadata=metadata,
                                        **self.parent.kwargs_fields)
        #    self.error = None
        #except Exception as error:
        #    self.error = error


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
def nwbn_conversion_gui(metafile=None, conversion_module='', source_paths={},
                        kwargs_fields={}, show_add_del=False):
    """Sets up QT application."""
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)  # instantiate a QtGui (holder for the app)
    ex = Application(metafile=metafile,
                     conversion_module=conversion_module,
                     source_paths=source_paths,
                     kwargs_fields=kwargs_fields,
                     show_add_del=show_add_del)
    sys.exit(app.exec_())
