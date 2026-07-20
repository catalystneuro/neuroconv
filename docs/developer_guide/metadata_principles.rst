.. _metadata_principles:

Metadata Principles
===================

This document states the rules that govern the ``metadata`` dictionary across every modality: what an
interface may report from its source format, where the values that NWB requires but the source does
not supply come from instead, and how the dictionary is allowed to flow through the write call stack. It is intended
for developers contributing new interfaces or modifying existing ones.

The modality-specific pages (:ref:`ophys_metadata_structure`, :ref:`events_metadata_structure`,
:ref:`fiber_photometry_metadata_structure`) describe the *shape* of each modality's metadata. This
page describes the rules all of those shapes obey.


Interface metadata is faithful to the source
----------------------------------------------

**Faithful means that every value an interface reports comes from something the source format actually
recorded.** If the source did not say it, the interface does not report it.

``get_metadata()`` is therefore an extraction method, not a convenience one. It returns what the
interface read out of the source format and nothing else: no defaults, no placeholders, and no empty
scaffold for the user to fill in. Whatever a conversion cannot answer from the source is the user's to
supply, and an interface that answers on their behalf has removed their chance to notice.

Concretely, if the source carries no value for a field:

- **Omit the key.** Do not emit ``"description": ""``, ``"location": "unknown"``, or an empty
  sub-dictionary. An absent key says "the source did not tell us"; an empty or sentinel value says
  "the source told us, and this is the answer", and those are different claims.
- **Do not return a structure the source does not evidence.** A segmentation file that carries no
  optical information should not produce an ``ImagingPlane`` with an ``indicator`` and an
  ``excitation_lambda``; a recording with no probe information should not produce an
  ``ElectrodeGroup`` at a named ``location``. The structure implies the source described these
  things.

A placeholder in the dictionary makes it impossible for anything downstream to tell whether a value
came from the source, the user, or NeuroConv. Warning about it at write time does not help, since the
value is written regardless.

An un-annotated conversion therefore produces fields the user still has to fill in, and NWB Inspector
reports them. That is intended: fill them in rather than quieting the report with something that reads
like an answer.

See `issue #1557 <https://github.com/catalystneuro/neuroconv/issues/1557>`_ for the discussion.

Staying faithful is not the whole story, though. Some of what a source leaves out is genuinely
required by NWB, and a file cannot be written without it, so a value has to come from somewhere even
when the interface reports none.


Placeholders for required fields
---------------------------------

NWB requires some fields whether or not anyone supplied them: a ``Device`` needs a name, a
``DynamicTable`` a description. Where the source has no value, NeuroConv writes a placeholder
rather than raising, since much of what NWB requires is not in the source formats.

A placeholder does reach the file, so prefer one that NWB Inspector already flags (see its
`placeholder best practice
<https://nwbinspector.readthedocs.io/en/dev/best_practices/general.html#best-practice-placeholders>`_).
Where no check exists for the field yet, adding one is the better fix than picking a value that passes
quietly. Keep the string fallbacks few and centralized in one factory per modality
(`ophys <https://github.com/catalystneuro/neuroconv/blob/a02fb353ea19112b7ef81542f5f05359f3b5498f/src/neuroconv/tools/roiextractors/roiextractors.py#L83>`_,
`ecephys <https://github.com/catalystneuro/neuroconv/blob/a02fb353ea19112b7ef81542f5f05359f3b5498f/src/neuroconv/tools/spikeinterface/spikeinterface.py#L84>`_) so they can change in
one place.

See `nwb-schema issue #672 <https://github.com/NeurodataWithoutBorders/nwb-schema/issues/672>`_ for
the discussion.


How modality pipelines handle metadata propagation
----------------------------------------------------

A **modality pipeline** is the ``add_*_to_nwbfile`` call stack that turns an extractor (or an
interface's parsed source) plus a metadata dictionary into NWB objects: the ophys functions in
``tools/roiextractors``, the ecephys functions in ``tools/spikeinterface``, and their equivalents for
icephys, behavior, and events. An interface's ``add_to_nwbfile`` delegates to one of them, and a
converter runs several in sequence over the same file and, usually, the same metadata dictionary.

That sharing is what makes propagation a question. The dictionary the user hands in is read at many
depths by functions that do not know which interface is running or what a previous one already wrote,
so the rules below govern what those functions may read from it, what they may write to it, and where
the values NWB requires but nobody supplied are allowed to come from.

Three principles govern the dictionary as it moves through a pipeline, in every modality:

1. **Single source of truth.** Keep one dictionary holding a modality's placeholders (the placeholder
   factory). It is the authoritative reference for default values, and reading from it is explicit.
2. **Immutable metadata.** The user-supplied ``metadata`` passes through the entire call stack without
   modification. A function that reads metadata must never write back into it. This is the principle
   most easily violated by accident.
3. **Targeted defaults.** Fetch defaults only at the point of object creation, and only for the values
   the object being created actually requires. Do not pre-fill the dictionary so that lookups resolve
   uniformly; that both mutates the caller's input and obscures which values came from the user.

The motivation is debuggability. Deep in the call stack it must remain clear whether a value came from
the user or from a default, and a caller who reuses one metadata dictionary across several interfaces
(the normal converter pattern) must not have placeholder entries silently injected into it by an
earlier ``add_*`` call.

See `issue #1511 <https://github.com/catalystneuro/neuroconv/issues/1511>`_ for the discussion.


Checklist for a new interface
------------------------------

When writing or reviewing an interface:

- Every key ``get_metadata()`` returns corresponds to something read from the source.
- No key holds ``""``, ``{}``, ``None``, ``np.nan``, ``"unknown"``, or any other sentinel.
- No object is returned that the source gives no evidence for: no imaging plane without optical
  information, no electrode group without probe information, no fiber without a fiber.
- Required NWB fields with no source value are filled in ``add_to_nwbfile``, where the object is built.
- The metadata dictionary is not modified anywhere in the call stack.
