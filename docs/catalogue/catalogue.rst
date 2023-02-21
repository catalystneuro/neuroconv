.. _catalogue:

Catalogue of Past Projects
==========================

The conversion gallery gives simple examples of conversions from simple combinations of formats.

Some neurophysiology experiments require more diverse combinations of interfaces as well as more exotic functionalities to be NWB and DANDI compatible.

This catalogue contains references and short descriptions for a number of real examples of pipelines used by labs to generate NWB files, many of which are now published on DANDI!

If it sounds as if any of the projects in this catalogue might be similar to your own experiments, it might be worth checking out how they implemented things and asking questions by raising Issues on the respective repositories.

..note:: It is likely that each project pinned itself to a specific minor version of NeuroConv, or its predecessor, nwb-conversion-tools (NCT). We have organized each pipeline according to the version used in descending order (newest version first).



NeuroConv v0.2
--------------

`Ahrens Lab <https://ahrenslab.org>`_: `ahrens-lab-to-nwb <https://github.com/catalystneuro/ahrens-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Ahrens lab was interested in publically sharing the imaging data corresponding to the high-impact publication `Mu Y, Bennett DV, Rubinov M, Narayan S, Yang CT, Tanimoto M, Mensh BD, Looger LL, Ahrens MB. Glia Accumulate Evidence that Actions Are Futile and Suppress Unsuccessful Behavior. Cell. 2019 <https://www.cell.com/cell/fulltext/S0092-8674(19)30621-X?_returnURL=https%3A%2F%2Flinkinghub.elsevier.com%2Fretrieve%2Fpii%2FS009286741930621X%3Fshowall%3Dtrue>`_ and hosting the data on the DANDI archive. In this experiment, paralyzed zebrafish were place in a virtual reality environment which systemetically responded to their attempts to swim by either mimicing movement effects within the environment or not (test of futility). While the subject attempts to engage in swimming behaviors, a light-sheet microscope performs whole-brain scans tracking flourescence activity of neurons, glia, or both dependeing on the session.

`Murthy Lab <https://ahrenslab.org/)>`_: `murthy-lab-to-nwb <https://github.com/catalystneuro/murthy-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Murthy lab studies fly interactions combined with optical imaging techniques. This project specifically focused on an upcoming paper related to mating behaviors. The most complex aspects of this pipeline include multiple subjects, pose estimation through SLEAP, and visual stimulus reconstruction (from the fly's perspective).

`Fee Lab <https://ahrenslab.org/>`_: `fee-lab-to-nwb <https://github.com/catalystneuro/fee-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Fee lab was interested in sharing data related to several upcoming publications utilizing both optical imaging and extracellular electrophysiology. The work with this lab focused largely on encoding and visualization of complex hierarchical audio signals which are compared directly to temporally aligned neural activity.



NCT v0.9
--------

`Buzsáki Lab <https://buzsakilab.com/wp/>`_: `buzsaki-lab-to-nwb <https://github.com/catalystneuro/buzsaki-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This project was a part of the Ripple U19 conversion of extracellular electrophysiology data to NWB format, including final publishing of each dataset on DANDI. Currently spans 7 major publications and over 14 TB of data on the `DANDI Archive <https://www.dandiarchive.org/>`_. Most of the data consists of raw recordings, LFP, spike sorted units, and behavior with can consist of a mix of mental state tracking, position tracking through mazes, and trial stimulus events.

`Shenoy Lab <https://npsl.sites.stanford.edu>`_: `shenoy-lab-to-nwb <https://github.com/catalystneuro/shenoy-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Shenoy lab is one of the pioneers in developing BCIs for people with paralysis. They are part of the `BrainGate <https://www.braingate.org>`_ team
and were the winners of the 2019 `BCI award <https://www.bci-award.com/2019>`_.
They use extracellular recordings from Utah arrays and Neuropixels in primates.

`Brody Lab <http://brodylab.org/>`_: `brody-lab-to-nwb <https://github.com/catalystneuro/brody-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Brody lab has a long history with extracellular electrophysiology experiements spanning multiple acquisition systems. This project served two purposes - to allow the conversion of older data from Neuralynx and SpikeGadgets to NWB, and also their newer, larger data using Neuropixels (SpikeGLX). These recordings, some of which exceeded more than 250 GB (several hours worth!), were paired with rich trials tables containing catagorical events and temporal stimuli.



NCT v0.8
--------

`Feldman Lab <https://www.feldmanlab.org/>`_: `feldman-lab-to-nwb <https://github.com/catalystneuro/feldman-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Feldman lab utilizes a Neuropixels (SpikeGLX) system along with multiple sophisticated behavior systems for manipulating whisker stimulation in mice. These give rise to very complex trials tables tracking multiple event times throughout the experiments, including multiple event trains within trials.

Hussaini Lab: `hussaini-lab-to-nwb <https://github.com/catalystneuro/hussaini-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Movson Lab <https://www.cns.nyu.edu/labs/movshonlab/>`_: `movshon-lab-to-nwb <https://github.com/catalystneuro/movshon-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



NCT v0.7.0
----------

`Tank Lab <https://pni.princeton.edu/faculty/david-tank>`_: `tank-lab-to-nwb <https://github.com/catalystneuro/tank-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Neuropixel (SpikeGLX) recordings of subjects navigating a virtual reality! Behavior contains a huge variety of NWB data types including positional and view angle over time,  collision detection, and more! Paired with a `specific extension <https://github.com/catalystneuro/ndx-tank-metadata>`_ for parsing experiment metadata.

`Groh Lab <https://www.uni-heidelberg.de/izn/researchgroups/groh/>`_: `mease-lab-to-nwb <https://github.com/catalystneuro/mease-lab-to-nwb>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Utilizing the CED recording interface, this project paired ecephys channels with optogenetic stimulation via laser pulses, and mechnical pressure stimulation over time - all of which are channels of data extracted from the common `.smrx` files!

`Giocomo Lab <https://giocomolab.weebly.com/>`_: `giocomo-lab-to-nwb <https://github.com/catalystneuro/giocomo-lab-to-nwb/tree/master/giocomo_lab_to_nwb/mallory21>`_
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


Other examples of NWB pipelines
-------------------------------
* `Axel Lab <https://www.axellab.columbia.edu/>`_: `axel-lab-to-nwb <https://github.com/catalystneuro/axel-lab-to-nwb>`_
* `Brunton Lab <https://www.bingbrunton.com/>`_: `brunton-lab-to-nwb <https://github.com/catalystneuro/brunton-lab-to-nwb>`_
* `Buffalo Lab <https://buffalomemorylab.com/>`_: `buffalo-lab-data-to-nwb <https://github.com/catalystneuro/buffalo-lab-data-to-nwb>`_
* `Jaeger Lab <https://scholarblogs.emory.edu/jaegerlab/>`_: `jaeger-lab-to-nwb <https://github.com/catalystneuro/jaeger-lab-to-nwb>`_
* `Tolias Lab <https://toliaslab.org/>`_: `tolias-lab-to-nwb <https://github.com/catalystneuro/tolias-lab-to-nwb>`_
