.. _fiber_photometry_device_models:

Fiber photometry hardware specification catalogue
=================================================

.. This page is generated from ``src/neuroconv/reference_data/fiber_photometry_device_models.json``
   by ``docs/user_guide/_generate_fiber_photometry_device_models.py``. Edit the catalogue, not this file.

No fiber photometry format records what hardware produced the recording. A Doric file names the
console, not the modules plugged into it; TDT, Neurophotometrics and comma-separated-value exports
carry no device specifications at all. The numerical aperture of a fiber, the wavelength range of an
excitation source and the gain of a photodetector are therefore not readable from the data, and
``get_metadata()`` will never supply them.

They are, however, published. The tables below collect the specifications the vendors state for
common fiber photometry hardware, each row carrying the page its values came from, so a device model
can be filled by finding the part rather than by inventing numbers.

Filling the metadata
--------------------

There is one function per model type. Look up your part by its manufacturer and part number, and put
what comes back into the metadata ``get_metadata()`` returned:

.. code-block:: python

    from neuroconv.tools.fiber_photometry_hardware_catalogue import get_reference_optical_fiber_model

    metadata = interface.get_metadata()
    metadata["DeviceModels"]["optical_fiber_model"] = get_reference_optical_fiber_model(
        manufacturer="Thorlabs", part="CFMC12L20"
    )

The others are ``get_reference_excitation_source_model``, ``get_reference_photodetector_model``,
``get_reference_band_optical_filter_model``, ``get_reference_edge_optical_filter_model`` and
``get_reference_dichroic_mirror_model``.

A part is addressed by all three of model type, manufacturer and part number, because neither of the
last two identifies it alone. A part number means something only relative to who issued it, and short
ones like ``2151`` or ``PS1`` are exactly the kind that collide. One product commonly yields several
models, too: a fluorescence mini-cube is filters and dichroic mirrors at once, and an FP3002 is
excitation sources and a detector, so the type is what separates ``FMC4 emission 500-550 nm`` from the
cube it sits in. Manufacturer and part are matched case-insensitively.

Parts whose vendor publishes no model number are addressed by their product name, and ``name`` sets
what the model is written as when the default, its class name, does not suit:

.. code-block:: python

    metadata["DeviceModels"]["excitation_source_model"] = get_reference_excitation_source_model(
        manufacturer="Neurophotometrics",
        part="FP3002 470 nm",
        name="isosbestic_source_model",
    )

What comes back is an ordinary dictionary, so edit it as you would any other metadata: a value you
read off your own hardware simply replaces the published one. ``list_reference_device_models()``
returns every part covered, filtered by manufacturer or by model type.

Before you use a row
--------------------

Check the part against the rig that produced the recording. Product lines change, so treat the source
link as the authority rather than the table. Per-lab customization is common, and fiber photometry
rigs mix vendors freely, so a Doric console frequently runs a Newport photoreceiver and Thorlabs
fibers. A vendor-branded row is not evidence about what a given laboratory physically had.

Photodetector gain is the weakest field throughout. It is a switchable setting on the Doric and
Newport detectors, printed without a unit by Tucker-Davis Technologies, and unpublished for the
Neurophotometrics camera, so leave it unset unless you read it off your own device configuration.


Optical fibers
--------------

Doric parts are keyed by the ordering-code fragment that describes the fiber, the core and cladding diameters followed by the numerical aperture. The complete ordering code also encodes the ferrule type and the length, so check yours rather than assuming the fragment is the whole part number.

.. list-table::
   :widths: 10 14 7 7 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Numerical aperture
     - Core diameter (um)
     - Ferrule diameter (mm)
     - Notes
     - Source
   * - Doric Lenses
     - ``200/240-0.22``
     - 0.22
     - 200
     - \-
     - Glass fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``200/245-0.37``
     - 0.37
     - 200
     - \-
     - Glass fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``400/470-0.37``
     - 0.37
     - 400
     - \-
     - Glass fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``200/230-0.48``
     - 0.48
     - 200
     - \-
     - Polymer fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``400/430-0.48``
     - 0.48
     - 400
     - \-
     - Polymer fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``200/250-0.66``
     - 0.66
     - 200
     - \-
     - Borosilicate fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Doric Lenses
     - ``400/430-0.66``
     - 0.66
     - 400
     - \-
     - Borosilicate fiber.
     - `page <https://neuro.doriclenses.com/products/mono-fiber-optic-cannulas>`__
   * - Thorlabs
     - ``CFMC12L20``
     - 0.39
     - 200
     - 2.5
     - Implantable cannula, 20 mm.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=CFMC12L20>`__
   * - Thorlabs
     - ``CFMC22L05``
     - 0.22
     - 200
     - 2.5
     - Implantable cannula, 5 mm.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=CFMC22L05>`__
   * - Thorlabs
     - ``CFMLC52L20``
     - 0.5
     - 200
     - 1.25
     - Implantable cannula, 20 mm.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=CFMLC52L20>`__
   * - Thorlabs
     - ``CFMC54L20``
     - 0.5
     - 400
     - 2.5
     - Implantable cannula, 20 mm.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=CFMC54L20>`__
   * - Thorlabs
     - ``FT200UMT``
     - 0.39
     - 200
     - \-
     - Bare multimode fiber, no ferrule.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=FT200UMT>`__
   * - Thorlabs
     - ``FP200URT``
     - 0.5
     - 200
     - \-
     - Bare multimode fiber, no ferrule.
     - `page <https://www.thorlabs.com/thorproduct.cfm?partnumber=FP200URT>`__
   * - RWD Life Science
     - ``R-FOC-BF200C-39NA``
     - 0.39
     - 200
     - 2.5
     - Black series.
     - `page <https://www.rwdstco.com/product-item/fiber-optic-cannulae-with-ceramic-ferrule/>`__
   * - RWD Life Science
     - ``R-FOC-BF400C-39NA``
     - 0.39
     - 400
     - 2.5
     - Black series.
     - `page <https://www.rwdstco.com/product-item/fiber-optic-cannulae-with-ceramic-ferrule/>`__
   * - RWD Life Science
     - ``R-FOC-L200C-22NA``
     - 0.22
     - 200
     - 1.25
     - White series.
     - `page <https://www.rwdstco.com/product-item/fiber-optic-cannulae-with-ceramic-ferrule/>`__
   * - RWD Life Science
     - ``R-FOC-F400C-50NA``
     - 0.5
     - 400
     - 2.5
     - White series.
     - `page <https://www.rwdstco.com/product-item/fiber-optic-cannulae-with-ceramic-ferrule/>`__
   * - Tucker-Davis Technologies
     - ``LxFX-KIT-2C``
     - 0.5
     - \-
     - \-
     - Two-channel kit. The core diameter is chosen at ordering (200, 400 or 600 um).
     - `page <https://www.tdt.com/docs/fiber-photometry-user-guide/optical-connections/>`__
   * - Tucker-Davis Technologies
     - ``LxFX-KIT-3C``
     - 0.5
     - \-
     - \-
     - Three-channel kit. The core diameter is chosen at ordering (200, 400 or 600 um).
     - `page <https://www.tdt.com/docs/fiber-photometry-user-guide/optical-connections/>`__


Excitation sources
------------------

Every source here is a one-photon light-emitting diode, so ``source_type`` and ``excitation_mode`` are filled with those values and left out of the table. Tucker-Davis Technologies publishes only a nominal center wavelength for the Lux sources, with no bandwidth, so those rows carry the center in their description and no range at all. Neurophotometrics publishes no model number for the FP3002's onboard sources, so those parts are looked up by their product name instead.

Doric renumbered its connectorized light-emitting diodes in a 2025 Generation-2 redesign, prefixing the codes with ``CLED_G2_`` and moving the blue channel from 465 to 470 nm. Both generations are listed, because a rig built before the change carries ``CLED_465`` and the bare code ``CLED_470`` has never been a Doric ordering code at all.

.. list-table::
   :widths: 10 14 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Wavelength range (nm)
     - Notes
     - Source
   * - Doric Lenses
     - ``CLED_G2_405``
     - 399 to 411
     - Isosbestic control. The range is the nominal center plus the published 12 nm bandwidth.
     - `page <https://neuro.doriclenses.com/products/connectorized-led-1>`__
   * - Doric Lenses
     - ``CLED_465``
     - 452.5 to 477.5
     - The '465 nm' of a Doric 405/465 system. Retired in the 2025 Generation-2 redesign, which moved the blue channel to 470 nm.
     - `page <https://doriclenses.com/downloads/UserManual/UserManual_LED_Light_Source_V2.1.1.pdf>`__
   * - Doric Lenses
     - ``CLED_G2_470``
     - 457 to 484
     - Generation-2 blue channel. It replaced the discontinued CLED_465, so a 405/465 system built before 2025 carries that part instead.
     - `page <https://neuro.doriclenses.com/products/connectorized-led-1>`__
   * - Doric Lenses
     - ``CLED_G2_560``
     - 510 to 610
     - Red-shifted indicators. The published 100 nm bandwidth makes this range approximate.
     - `page <https://neuro.doriclenses.com/products/connectorized-led-1>`__
   * - Tucker-Davis Technologies
     - ``Lx405``
     - \-
     - Isosbestic control.
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Tucker-Davis Technologies
     - ``Lx415``
     - \-
     -
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Tucker-Davis Technologies
     - ``Lx465``
     - \-
     -
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Tucker-Davis Technologies
     - ``Lx560``
     - \-
     -
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Neurophotometrics
     - ``FP3002 415 nm``
     - 400 to 425
     - Isosbestic control. The range is the published optical passband, not a certified bandwidth.
     - `page <https://www.mbfbioscience.com/products/fp3002/>`__
   * - Neurophotometrics
     - ``FP3002 470 nm``
     - 445 to 486
     - Green indicators such as GCaMP and dLight. The range is the optical passband.
     - `page <https://www.mbfbioscience.com/products/fp3002/>`__
   * - Neurophotometrics
     - ``FP3002 560 nm``
     - 535 to 569
     - Red-shifted indicators such as RCaMP. The range is the optical passband.
     - `page <https://www.mbfbioscience.com/products/fp3002/>`__


Optical filters
---------------

Doric's fluorescence mini-cubes carry the filters that set a rig's actual excitation and emission bands, and publish them as passbands. Every one is a bandpass filter, so ``filter_type`` is filled with that and left out of the table, and the center and bandwidth below are the published passband restated in the fields the model provides, with the interval itself kept in each row's description. A mini-cube's bands are chosen when it is ordered, and its ordering code records the ones it was built with, so these rows describe the GCaMP configuration each product page documents rather than every cube of that model.

The cubes' dichroic mirrors are not shipped. Doric describes them in prose, and publishes no cut-on wavelength, transmission band or angle of incidence for them on the product pages, in the mini-cube manuals or in the mechanical drawings. Inferring an edge from the surrounding passbands would be a guess, so there is nothing here to look up.

.. list-table::
   :widths: 10 14 7 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Center wavelength (nm)
     - Bandwidth (nm)
     - Notes
     - Source
   * - Doric Lenses
     - ``FMC4 excitation 400-410 nm``
     - 405
     - 10
     - Isosbestic band. The FMC4 offers four selectable isosbestic passbands; this is one of them.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC4 excitation 410-420 nm``
     - 415
     - 10
     - Isosbestic band. The FMC4 offers four selectable isosbestic passbands; this is one of them.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC4 excitation 421-433 nm``
     - 427
     - 12
     - Isosbestic band. The FMC4 offers four selectable isosbestic passbands; this is one of them.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC4 excitation 433-445 nm``
     - 439
     - 12
     - Isosbestic band. The FMC4 offers four selectable isosbestic passbands; this is one of them.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC4 excitation 460-490 nm``
     - 475
     - 30
     - Functional excitation, the channel a 405/465 system calls its 465 nm one.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC4 emission 500-550 nm``
     - 525
     - 50
     - GCaMP emission. Out-of-band rejection is optical density 5.
     - `page <https://neuro.doriclenses.com/products/fmc4-gcamp>`__
   * - Doric Lenses
     - ``FMC5 excitation 460-490 nm``
     - 475
     - 30
     - Green excitation.
     - `page <https://neuro.doriclenses.com/products/fmc5>`__
   * - Doric Lenses
     - ``FMC5 emission 500-550 nm``
     - 525
     - 50
     - Green emission.
     - `page <https://neuro.doriclenses.com/products/fmc5>`__
   * - Doric Lenses
     - ``FMC5 excitation 540-570 nm``
     - 555
     - 30
     - Red excitation, the channel a system calls its 560 nm one.
     - `page <https://neuro.doriclenses.com/products/fmc5>`__
   * - Doric Lenses
     - ``FMC5 emission 580-680 nm``
     - 630
     - 100
     - Red emission.
     - `page <https://neuro.doriclenses.com/products/fmc5>`__


Dichroic mirrors
----------------

The dichroic is what sets a rig's spectral geometry, splitting excitation from the returning fluorescence, and only the vendors who sell them as parts publish an edge. Doric is not among them: it describes the dichroics inside its mini-cubes but states no wavelength for any of them, so a stock Doric or Tucker-Davis rig cannot fill one of these rows from public information. Every value here is the vendor's published figure at the angle of incidence the vendor specifies, so a part mounted at a different angle has a different edge in practice.

.. list-table::
   :widths: 10 14 7 7 7 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Cut-on (nm)
     - Cut-off (nm)
     - Reflection band (nm)
     - Transmission band (nm)
     - Notes
     - Source
   * - Thorlabs
     - ``DMLP425``
     - 425
     - \-
     - 380 to 410
     - 440 to 800
     - Isosbestic-band splitter.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMLP490``
     - 490
     - \-
     - 380 to 475
     - 505 to 800
     -
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMLP505``
     - 505
     - \-
     - 380 to 490
     - 520 to 800
     - The usual GCaMP-band splitter of this family.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMLP550``
     - 550
     - \-
     - 380 to 533
     - 565 to 800
     -
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMLP567``
     - 567
     - \-
     - 380 to 550
     - 584 to 800
     - Sits at the red-shifted indicator edge (RCaMP, jRGECO).
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMLP605``
     - 605
     - \-
     - 470 to 590
     - 620 to 800
     - Separates red emission from 560 to 590 nm excitation.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=3313>`__
   * - Thorlabs
     - ``DMSP490``
     - \-
     - 490
     - 505 to 800
     - 380 to 475
     - Shortpass counterpart of the DMLP490; Thorlabs calls this figure the cutoff wavelength.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=9240>`__
   * - Thorlabs
     - ``DMSP505``
     - \-
     - 505
     - 520 to 800
     - 390 to 490
     - Shortpass counterpart of the DMLP505.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=9240>`__
   * - Thorlabs
     - ``DMSP567``
     - \-
     - 567
     - 584 to 800
     - 390 to 550
     - Shortpass counterpart of the DMLP567.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=9240>`__
   * - Semrock
     - ``FF409-Di03-25x36``
     - 409
     - \-
     - 327 to 404
     - 415 to 950
     - Edge at the 405 to 415 nm isosbestic excitation.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__
   * - Semrock
     - ``FF470-Di01-25x36``
     - 470
     - \-
     - 350 to 462.5
     - 477 to 950
     - Edge at the 465 to 470 nm GCaMP excitation line.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__
   * - Semrock
     - ``FF495-Di03-25x36``
     - 495
     - \-
     - 350 to 488
     - 502 to 950
     - The classic GCaMP-band epifluorescence dichroic. Discontinued, so it describes existing rigs rather than new ones.
     - `page <https://www.idex-hs.com/store/product-detail/ff495_di03_25x36/fl-007145>`__
   * - Semrock
     - ``FF495-Di04-25x36``
     - 495
     - \-
     - 350 to 488
     - 502 to 950
     - Current replacement for the FF495-Di03 at the same edge.
     - `page <https://www.idex-hs.com/store/product-detail/ff495_di04_25x36/fl-439557>`__
   * - Semrock
     - ``FF506-Di03-25x36``
     - 506
     - \-
     - 350 to 500
     - 513 to 950
     - Green-emission edge for a wider 470 nm excitation band.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__
   * - Semrock
     - ``FF562-Di03-25x36``
     - 562
     - \-
     - 350 to 555
     - 569 to 950
     - Edge just above the 560 nm excitation used for red-shifted indicators.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__
   * - Semrock
     - ``FF580-FDi01-25x36``
     - 580
     - \-
     - 350 to 570
     - 590.8 to 950
     - Image-splitting dichroic, in the band a two-colour rig uses to split green from red.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__
   * - Semrock
     - ``FF593-Di03-25x36``
     - 593
     - \-
     - 350 to 585
     - 601 to 950
     - Red-channel edge for jRGECO and RCaMP emission.
     - `page <https://www.idex-hs.com/docs/default-source/catalogs/semrock-catalog.pdf>`__


Edge filters
------------

Longpass and shortpass filters, specified at normal incidence. Never read a cut wavelength off a part number: Semrock's ``BLP01-488R-25`` is named for the 488 nm laser line it serves and its published edge is 500 nm. None of these vendors publishes the slope figures the model also accepts, so those fields stay empty.

.. list-table::
   :widths: 10 14 7 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Filter type
     - Cut wavelength (nm)
     - Notes
     - Source
   * - Thorlabs
     - ``FELH0500``
     - Longpass
     - 500
     - Specified at normal incidence.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6082>`__
   * - Thorlabs
     - ``FELH0550``
     - Longpass
     - 550
     - Specified at normal incidence.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6082>`__
   * - Thorlabs
     - ``FELH0600``
     - Longpass
     - 600
     - Emission filter for red-shifted indicators. Specified at normal incidence.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6082>`__
   * - Thorlabs
     - ``FESH0500``
     - Shortpass
     - 500
     - Often used to clean up excitation. Specified at normal incidence.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6082>`__
   * - Thorlabs
     - ``FESH0550``
     - Shortpass
     - 550
     - Specified at normal incidence.
     - `page <https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6082>`__
   * - Semrock
     - ``BLP01-488R-25``
     - Longpass
     - 500
     - The published edge is 500 nm, not the 488 in the part number, which names the laser line it is built for. Discontinued.
     - `page <https://www.idex-hs.com/store/product-detail/blp01_488r_25/fl-008552>`__


Photodetectors
--------------

A gain is shipped only where the vendor publishes a single figure for it, which rules out the two detectors whose gain is a setting rather than a specification.

.. list-table::
   :widths: 10 14 7 7 7 45 7
   :header-rows: 1

   * - Manufacturer
     - Part
     - Detector type
     - Wavelength range (nm)
     - Gain
     - Notes
     - Source
   * - Doric Lenses
     - ``Fluorescence Detector``
     - photodiode
     - \-
     - \-
     - No stock keeping unit is printed, so the key names the product. The gain is switchable, so set it from the setting you recorded with.
     - `page <https://neuro.doriclenses.com/products/doric-fluorescence-detector>`__
   * - Newport
     - ``2151``
     - photodiode
     - 320 to 1050
     - 1e11 V/W
     - Resold with Doric systems. The manual gives the range from 300 nm where the product page gives 320.
     - `page <https://www.newport.com/p/2151>`__
   * - Tucker-Davis Technologies
     - ``PS1``
     - photodiode
     - 320 to 1100
     - 1e10
     - The datasheet prints the gain with no unit, so no gain unit is shipped.
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Tucker-Davis Technologies
     - ``PS2``
     - photodiode
     - 320 to 1100
     - 1e10
     - Published as the PS1, with roughly twice the signal-to-noise ratio.
     - `page <https://www.tdt.com/product/lux-leds-and-sensors/>`__
   * - Neurophotometrics
     - ``FP3002 camera``
     - sCMOS
     - \-
     - \-
     - The sensor's own make, model and gain are unpublished, so the manufacturer names the system vendor.
     - `page <https://www.mbfbioscience.com/products/fp3002/>`__


Parts with no representable model
---------------------------------

These specifications are published, but they do not fit the fields the extension defines, so they are
not shipped as rows. Fill them by hand, deciding for yourself what to record.


**FP3002 patch cord, 8-branch bundle** (Neurophotometrics, OpticalFiberModel)

   Published: numerical aperture 0.37 to 0.4, core diameter 200 um. The vendor publishes the numerical aperture as a range rather than a value, and OpticalFiberModel requires a single number. Pick the value that matches the cord you have, or state the range in the description.
   `Source <https://www.mbfbioscience.com/products/fp3002/>`__

**FP3002 patch cord, 4-branch bundle** (Neurophotometrics, OpticalFiberModel)

   Published: numerical aperture 0.37 to 0.4, core diameter 400 um. The vendor publishes the numerical aperture as a range rather than a value, and OpticalFiberModel requires a single number.
   `Source <https://www.mbfbioscience.com/products/fp3002/>`__
