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

These rules constrain **interfaces and converters**, not users. A user building a file or a conversion
script should know the experiment and supply every value they can; NeuroConv's job is only to convert
what the source recorded, so an interface or converter must not assert a value the source does not
contain, any more than it would measure a quantity the instrument did not. The distinction matters
because a value an automated tool invents is indistinguishable, once written, from one the experimenter
deliberately entered.


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

See `issue #1557 <https://github.com/catalystneuro/neuroconv/issues/1557>`_ for the discussion.

Staying faithful is not the whole story, though. Some of what a source leaves out is genuinely
required by NWB, and a file cannot be written without it, so a value has to come from somewhere even
when the interface reports none.


Placeholders for required fields
---------------------------------

Some of the fields that NWB objects require are not in the source format files at all: an
``ElectrodeGroup`` requires a ``location`` (the anatomical target), which the acquisition system does
not record, and an ``ImagingPlane`` requires an ``excitation_lambda``, which a bare imaging file
usually does not carry. Where a field has no source value, the decision is:

1. **Optional field: omit it.** If NWB does not require it, leave it out entirely rather than writing a
   blank or a guess. An absent optional field is correct, not incomplete.
2. **Required field: write a placeholder rather than raising.** A file cannot be written without it, and
   refusing to run until the user hand-fills every required field would make the common case a wall.
3. **When required, use a reasonable placeholder.** Prefer a value that at least makes sense for the
   field (``np.nan`` for a numeric wavelength), and better still one NWB Inspector already flags: it
   catches empty and known placeholder descriptions (see its `placeholder best practice
   <https://nwbinspector.readthedocs.io/en/dev/best_practices/general.html#best-practice-placeholders>`_).
4. **Keep placeholders centralized.** Put the string fallbacks in one factory per modality
   (`ophys <https://github.com/catalystneuro/neuroconv/blob/a02fb353ea19112b7ef81542f5f05359f3b5498f/src/neuroconv/tools/roiextractors/roiextractors.py#L83>`_,
   `ecephys <https://github.com/catalystneuro/neuroconv/blob/a02fb353ea19112b7ef81542f5f05359f3b5498f/src/neuroconv/tools/spikeinterface/spikeinterface.py#L84>`_)
   so they can change in one place.

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


.. _metadata_key_naming:

The ``metadata_key`` parameter
------------------------------

**A** ``metadata_key`` **is a namespace handle: it addresses an interface's entry within the metadata
dictionary, and nothing more.** It is not the NWB object's name. The object's ``name`` is a separate
field *inside* that entry for the user to edit; the key is only how the entry is reached.

Because the key is a handle and not a name:

1. **Use snake_case.** A key reads as a dictionary handle (``doric_events``, ``tdt_events``); CamelCase is
   reserved for the ``name`` of a neurodata type (``ElectricalSeries``, ``TrialOnset``), which lives
   *inside* the entry.
2. **Default to a fixed constant unless the format guarantees several instances.** When a session is a
   single source, one file or folder maps to one interface, so a stable constant (``"doric_events"``) is
   the readable default; two of them in one conversion is the rare case, resolved by passing
   ``metadata_key`` explicitly. Derive the key from a structural handle the format provides (a stream
   name, a channel) only where the format inherently produces many instances at once (SpikeGLX streams,
   multi-channel ophys) and collision is likely. Practicality beats purity.
3. **Be cautious inventing a uniqueness scheme.** A derived key becomes a contract the moment a user
   writes their metadata edits against it, so if the scheme later proves wrong and has to change, those
   users break. When an interface is likely to be instantiated several times but has no obvious
   distinguishing handle (a stream, a channel, something the user would recognize), be wary of inventing a
   highly specific scheme just to force uniqueness. For interfaces that consume common, generic formats
   (CSV, Parquet, NumPy, and the like), the file stem is a reasonable derived default. This is a gray
   area; explicit still beats implicit, so a user who needs a particular key can pass one.
4. **Type it** ``str | None`` **and resolve the default in** ``__init__``. Take
   ``metadata_key: str | None = None`` in the signature and compute the fallback in the body
   (``self.metadata_key = metadata_key or ...``), not as a literal signature default. A signature default
   can only be a static string, but the derived case in point 2 needs a value known only at construction
   (a stream, a channel, a file stem). Resolving it in ``__init__`` covers the constant and the derived
   case with one uniform pattern and keeps the fallback in a single place.


Checklist for a new interface
------------------------------

When writing or reviewing an interface:

- Every key ``get_metadata()`` returns corresponds to something read from the source.
- No key holds ``""``, ``{}``, ``None``, ``np.nan``, ``"unknown"``, or any other sentinel.
- No object is returned that the source gives no evidence for: no imaging plane without optical
  information, no electrode group without probe information, no fiber without a fiber.
- Required NWB fields with no source value are filled where the object is built, in the
  ``add_*_to_nwbfile`` call. That call may be a leaf interface writing its own objects, or a shared
  modality pipeline such as ``tools/spikeinterface`` and ``tools/roiextractors``.
- The metadata dictionary is not modified anywhere in the call stack.
- The ``metadata_key`` default is a snake_case constant, unless the format inherently produces several
  instances at once (then it is derived from a stable source handle).
- The ``metadata_key`` is typed ``str | None``, and its default is resolved in ``__init__``.
