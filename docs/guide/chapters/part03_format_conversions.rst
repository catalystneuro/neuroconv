Part 3, Automated Format Conversions
====================================

Conversion to NWB presents some challenges that come up again and again:

#. **Variety**. There is a large variety of proprietary formats in neurophysiology.
   Even within a single lab, you may have data from several different acquisition systems.
   Converting to NWB requires understanding how data is stored in that format,
   what metadata is present in the file, and where that metadata is within the proprietary
   files, as well as where they should go within NWB.
#. **Volume**. Neurophysiology data is large and the volume of individual session data
   is growing every year. HDF5 is designed to handle data at this scale, and has several
   tools that can help, including iterative read/write, chunking of large datasets,
   and streamlined compression/decompression. To dig into these tools yourself,
   see the PyNWB and MatNWB tutorials on advanced data I/O listed in the table above.

In order to make converting to NWB faster and less laborious (for our own team and for others),
we have developed an ecosystem of conversion tools that provide support for converting a
number of different proprietary formats to NWB. These tools handle the challenges of
variety and volume for the most common of data types.

Extracellular Electrophysiology
--------------------------------

A package within the SpikeInterface project called SpikeExtractors
has been developed to read extracellular electrophysiological data
from a variety of proprietary formats, for both raw and spike-sorted data.
We worked with the development team to robustly handle the technical details
of converting from these formats to NWB through the SpikeExtractors interface.
SpikeExtractors also leverages advanced I/O tools to automatically chunk large
datasets and apply lossless compression that is transparent to the user but can
substantially reduce the size of the NWB file. This package does not support
every electrophysiology data type, but does support a large number of them -
at the time of this writing, 21 raw formats and 18 spike-sorted formats.
Many of these formats are supported through a wrapper around python-neo reader classes.

To convert data using SpikeExtractors,
first install the package in python by running the following in Terminal::

    pip install spikeextractors

To convert raw data run in Python e.g.::

    from spikeextractors import NwbRecordingExtractor, BlackrockRecordingExtractor

    rx = BlackrockRecordingExtractor("dataset_path")
    NwbRecordingExtractor.write_recording(rx, "output_path.nwb")

(substituting BlackrockRecordingExtractor for whatever data acquisition format you have).
Depending on the format, you may be asked to install additional dependencies.
To convert spike-sorted data, run e.g.::

    from spikeextractors import NwbSortingExtractor, KlustaSortingExtractor

    rx = KlustaSortingExtractor("neo.kwik")
    NwbSortingExtractor.write_sorting(rx, "output_path.nwb")

To write both to the same file, you can simply direct both to the same output path.

Optical Neurophysiology
------------------------
We also developed a sister-package, `RoiExtractors`_, which does the same for
common raw and processed data types in optical neurophysiology, image stacks
and regions of interest (ROIs).

.. _RoiExtractors: https://github.com/catalystneuro/roiextractors

Intracellular Electrophysiology
--------------------------------
Conversion of common intracellular electrophysiology data types to NWB is
supported by the IPFX package, developed by the Allen Institute.
