To use from the command-line, you should first make sure that Python 3 is installed on your machine.

If you're using Windows, open 'cmd.exe', type 'python' and press Enter. This should give you some basic information about your
Python installation, including version number. This script is written to work with Python 3. You can then enter 'exit()' to return
to the command line prompt. If instead you get a message like 'python is not recognized as an internal command', that indicates
that either Python isn't installed on your machine, or it's not present in the PATH environment variable.

The default behavior of this script is to store the header information and data contained in the .rhd file in an object called 'a'.
This can be changed in the 'load_intan_rhd_format.py' file. The structure of this object is specified in the 'data_to_result.py' file.
For example, if you want to see the frequency parameters, you can add in 'print a['frequency_parameters'])' after the read_data()
function call. If you want to see the 50th sample from the 3rd amplifier channel, you can add in 'print(a['amplifier_data'][2][49])'
(Keeping in mind that Python uses 0-indexing. The first entry in a list is [0], the second entry is [1], and so on).