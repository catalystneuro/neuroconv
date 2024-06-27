.. _catalogue:

Catalogue of NeuroConv Projects
===============================

This is a catalogue of real-world examples of labs using NeuroConv to convert their data to NWB files. Each project
listed contains a description and a link to an open GitHub repository. Many of these projects use advanced
customization features beyond what is demonstrated in the conversion gallery.

.. note::

    Many of these projects have pinned a specific minor version of NeuroConv, or its predecessor, nwb-conversion-tools
    (NCT). We have organized each pipeline according to the version used in descending order (newest version first).

NeuroConv v0.3
--------------

`froemke-lab-to-nwb <https://github.com/catalystneuro/froemke-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
`Dr. Robert Froemke's Lab <https://med.nyu.edu/research/froemke-lab/>`_ at NYU converted electrophysiology,
photometry, and behavior to create dandisets:

* `000114 <https://dandiarchive.org/dandiset/000114>`_ associated with the Carcea et al. Nature 2021 paper,
  `"Oxytocin neurons enable social transmission of maternal behaviour" <https://www.nature.com/articles/s41586-021-03814-7>`_
* `000249 <https://dandiarchive.org/dandiset/000249>`_ associated with the Schiavo et al. Nature 2020 paper,
  `"Innate and plastic mechanisms for maternal behaviour in auditory cortex" <https://www.nature.com/articles/s41586-020-2807-6>`_.

NeuroConv v0.2
--------------

`ahrens-lab-to-nwb <https://github.com/catalystneuro/ahrens-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Dr. Misha Ahrens' lab <https://ahrenslab.org>`_ at Janelia converted the imaging data corresponding to the
publication `Mu Y, Bennett DV, Rubinov M, Narayan S, Yang CT, Tanimoto M, Mensh BD, Looger LL, Ahrens MB.
Glia Accumulate Evidence that Actions Are Futile and Suppress Unsuccessful Behavior. Cell. 2019
<https://doi.org/10.1016/j.cell.2019.05.050>`_
and shared the data on the DANDI archive. In this experiment, paralyzed zebra-fish were placed in a virtual reality
environment which systematically responded to their attempts to swim by either mimicking movement effects within the
environment or not (test of futility). While the subject attempts to engage in swimming behaviors, a light-sheet
microscope performs whole-brain scans tracking florescence activity of neurons, glia, or both depending on the session.

`murthy-lab-to-nwb <https://github.com/catalystneuro/murthy-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This project from `Dr. Mala Murthy's lab <https://mala-murthy.squarespace.com/>`_ at Princeton is focused on
converting data from an upcoming paper related to mating behaviors. This pipeline features multiple subjects, pose
estimation through SLEAP, and visual stimulus reconstruction (from the fly's perspective).

`fee-lab-to-nwb <https://github.com/catalystneuro/fee-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Dr. Michale Fee's lab at MIT <https://feelaboratory.org/michale-fee/>`_ is using this pipeline to convert and share
data related to several upcoming publications utilizing both optical imaging and extracellular electrophysiology.
These pipelines include encoding and visualization of complex hierarchical audio signals which are compared directly
to temporally aligned neural activity.

NCT v0.9
--------

`buzsaki-lab-to-nwb <https://github.com/catalystneuro/buzsaki-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These pipelines were built for `Dr. Gyorgy Buzsáki's lab at NYU <https://buzsakilab.com/wp/>`_ as part of the Ripple
U19 project. The pipelines provided here have converted and published data from 7 major publications with over 14 TB
of data combined on the `DANDI Archive <https://www.dandiarchive.org/>`_. Most of the data consists of raw
recordings, LFP, spike sorted units, and behavior with can consist of a mix of mental state tracking, position
tracking through mazes, and trial stimulus events.

`shenoy-lab-to-nwb <https://github.com/catalystneuro/shenoy-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These pipelines were built for `Dr. Krishna Shenoy's lab at Stanford <https://npsl.sites.stanford.edu>`_ and
illustrate conversion of extracellular recordings from Utah arrays and Neuropixels in primates.

`brody-lab-to-nwb <https://github.com/catalystneuro/brody-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This project with `Dr. Carlos Brody's lab at Princeton <http://brodylab.org/>`_ served two purposes: to allow the
conversion of older data from Neuralynx and SpikeGadgets to NWB, and also their newer, larger data using Neuropixels
(SpikeGLX). These recordings, some of which exceeded more than 250 GB (several hours worth!), were paired with rich
trials tables containing categorical events and temporal stimuli.

NCT v0.8
--------

`feldman-lab-to-nwb <https://github.com/catalystneuro/feldman-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Dr. Dan Feldman's lab at UC Berkeley <https://www.feldmanlab.org/>`_ utilizes a Neuropixels (SpikeGLX) system along
with multiple sophisticated behavior systems for manipulating whisker stimulation in mice. These give rise to very
complex trials tables tracking multiple event times throughout the experiments, including multiple event trains
within trials.


NCT v0.7.0
----------

`tank-lab-to-nwb <https://github.com/catalystneuro/tank-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this project, we worked with `Dr. David Tank's lab at Princeton <https://pni.princeton.edu/people/david-tank>`_ to
package data from Neuropixel (SpikeGLX) recordings of subjects navigating a virtual reality. Behavior contains a
variety of NWB data types including positional and view angle over time, collision detection, and more. This data
utilizes a custom `extension <https://github.com/catalystneuro/ndx-tank-metadata>`_ for parsing experiment metadata.

`mease-lab-to-nwb <https://github.com/catalystneuro/mease-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this project, we worked with the Groh Lab at Heidelberg University. Utilizing the CED recording interface, this project paired ecephys channels with optogenetic stimulation via laser pulses, and mechanical pressure stimulation over time - all of which are channels of data extracted from the common `.smrx` files!

`giocomo-lab-to-nwb <https://github.com/catalystneuro/giocomo-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This project from `Dr. Lisa Giocomo's lab at Stanford <https://giocomolab.weebly.com/>`_ features conversion pipelines
that handle raw and processed data from SpikeGLX and from calcium imaging.

Other examples of NWB pipelines
-------------------------------
* `Axel Lab <https://www.axellab.columbia.edu/>`_: `axel-lab-to-nwb <https://github.com/catalystneuro/axel-lab-to-nwb>`_
* `Brunton Lab <https://www.bingbrunton.com/>`_: `brunton-lab-to-nwb <https://github.com/catalystneuro/brunton-lab-to-nwb>`_
* `Buffalo Lab <https://buffalomemorylab.com/>`_: `buffalo-lab-data-to-nwb <https://github.com/catalystneuro/buffalo-lab-data-to-nwb>`_
* Hussaini Lab: `hussaini-lab-to-nwb <https://github.com/catalystneuro/hussaini-lab-to-nwb>`_
* `Jaeger Lab <https://scholarblogs.emory.edu/jaegerlab/>`_: `jaeger-lab-to-nwb <https://github.com/catalystneuro/jaeger-lab-to-nwb>`_
* `Movson Lab <https://www.cns.nyu.edu/labs/movshonlab/>`_: `movshon-lab-to-nwb <https://github.com/catalystneuro/movshon-lab-to-nwb>`_
* `Tolias Lab <https://toliaslab.org/>`_: `tolias-lab-to-nwb <https://github.com/catalystneuro/tolias-lab-to-nwb>`_
