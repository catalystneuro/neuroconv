.. _catalogue:

Catalogue of Past Projects
==========================

The conversion gallery gives simple examples of conversions from simple combinations of formats.

Some neurophysiology experiments require more diverse combinations of interfaces as well as more exotic functionalities to be NWB and DANDI compatible.

This catalogue contains references and short descriptions for a number of real examples of pipelines used by labs to generate NWB files, many of which are now published on DANDI!

If it sounds as if any of the projects in this catalogue might be similar to your own experiments, it might be worth checking out how they implemented things and asking questions by raising Issues on the respective repositories.

..note: It is likely that each project pinned itself to a specific version of NeuroConv, or its predecessor, nwb-conversion-tools (NCT). We have organized each pipeline according to the version used in descending order (newest version first)



NeuroConv v0.1.0
----------------

[Ahrens Lab](https://ahrenslab.org/): [ahrens-lab-to-nwb](https://github.com/catalystneuro/ahrens-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



[Murthy Lab](https://ahrenslab.org/): [murthy-lab-to-nwb](https://github.com/catalystneuro/murthy-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



[Fee Lab](https://ahrenslab.org/): [fee-lab-to-nwb](https://github.com/catalystneuro/fee-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^




NCT v0.9.3
----------

[Buzsáki Lab](https://buzsakilab.com/wp/): [buzsaki-lab-to-nwb](https://github.com/catalystneuro/buzsaki-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This project is an ongoing effort for the Ripple U19 conversion of extracellular electrophysiology data to NWB format, including final publishing of each dataset on DANDI. Currently spans 7 major publications and over 14 TB of data on the [DANDI Archive](https://www.dandiarchive.org/). Most of the data consists of raw recordings, LFP, spike sorted units, and behavior with can consist of a mix of mental state tracking, position tracking through mazes, and trial stimulus events.

[Shenoy lab](https://npsl.sites.stanford.edu): [shenoy-lab-to-nwb](https://github.com/catalystneuro/shenoy-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Shenoy lab is one of the pioneers in developing BCIs for people with paralysis. They are part of the [BrainGate](https://www.braingate.org) team
and were the winners of the 2019 [BCI award](https://www.bci-award.com/2019).
They use extracellular recordings from Utah arrays and Neuropixels in primates.



NCT v0.9.2
----------

[Brody Lab](http://brodylab.org/): [brody-lab-to-nwb](https://github.com/catalystneuro/brody-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Brody lab has a long history with extracellular electrophysiology experiements spanning multiple acquisition systems. This project served two purposes - to allow the conversion of older data from Neuralynx and SpikeGadgets to NWB, and also their newer, larger data using Neuropixels (SpikeGLX). These recordings, some of which exceeded more than 250 GB (several hours worth!), were paired with rich trials tables containing catagorical events and temporal stimuli.



NCT v0.8.10
-----------

[Feldman Lab](https://www.feldmanlab.org/): [feldman-lab-to-nwb](https://github.com/catalystneuro/feldman-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Feldman lab utilizes a Neuropixels (SpikeGLX) system along with multiple sophisticated behavior systems for manipulating whisker stimulation in mice. These give rise to very complex trials tables tracking multiple event times throughout the experiments, including multiple event trains within trials.



NCT v0.8.1
----------

Hussaini Lab: [hussaini-lab-to-nwb](https://github.com/catalystneuro/hussaini-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


[Movson lab](https://www.cns.nyu.edu/labs/movshonlab/): [movshon-lab-to-nwb](https://github.com/catalystneuro/movshon-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



NCT v0.7.0
----------

[Tank Lab](https://pni.princeton.edu/faculty/david-tank): [tank-lab-to-nwb](https://github.com/catalystneuro/tank-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Neuropixel (SpikeGLX) recordings of subjects navigating a virtual reality! Behavior contains a huge variety of NWB data types including positional and view angle over time,  collision detection, and more! Paired with a [specific extension](https://github.com/catalystneuro/ndx-tank-metadata) for parsing experiment metadata.

[Groh lab](https://www.uni-heidelberg.de/izn/researchgroups/groh/): [mease-lab-to-nwb](https://github.com/catalystneuro/mease-lab-to-nwb)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Utilizing the CED recording interface, this project paired ecephys channels with optogenetic stimulation via laser pulses, and mechnical pressure stimulation over time - all of which are channels of data extracted from the common `.smrx` files!

[Giocomo lab](https://giocomolab.weebly.com/): [giocomo-lab-to-nwb](https://github.com/catalystneuro/giocomo-lab-to-nwb/tree/master/giocomo_lab_to_nwb/mallory21)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


Other labs that use NWB (but not NeuroConv or NWBCT)
----------------------------------------------------
* [Axel lab](https://www.axellab.columbia.edu/): [axel-lab-to-nwb](https://github.com/catalystneuro/axel-lab-to-nwb)
* [Brunton lab](https://www.bingbrunton.com/): [brunton-lab-to-nwb](https://github.com/catalystneuro/brunton-lab-to-nwb)
* [Buffalo lab](https://buffalomemorylab.com/): [buffalo-lab-data-to-nwb](https://github.com/catalystneuro/buffalo-lab-data-to-nwb)
* [Jaeger lab](https://scholarblogs.emory.edu/jaegerlab/): [jaeger-lab-to-nwb](https://github.com/catalystneuro/jaeger-lab-to-nwb)
* [Tolias lab](https://toliaslab.org/): [tolias-lab-to-nwb](https://github.com/catalystneuro/tolias-lab-to-nwb)
