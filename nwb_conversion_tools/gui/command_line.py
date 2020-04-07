# Opens the NWB conversion GUI
# authors: Luiz Tauffer and Ben Dichter
# ------------------------------------------------------------------------------
from nwb_conversion_tools.gui.nwb_conversion_gui import nwb_conversion_gui
import os


def main():
    here = os.path.dirname(os.path.realpath(__file__))
    metafile = os.path.join(here, 'template_metafile.yml')
    conversion_module = os.path.join(here, 'template_conversion_module.py')

    source_paths = {}
    source_paths['file1'] = {'type': 'file', 'path': ''}
    source_paths['file2'] = {'type': 'file', 'path': ''}

    kwargs_fields = {}

    nwb_conversion_gui(
        metafile=metafile,
        conversion_module=conversion_module,
        source_paths=source_paths,
        kwargs_fields=kwargs_fields
    )
