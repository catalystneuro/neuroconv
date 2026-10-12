.. _deprecations:

Deprecating and removing an API
-------------------------------

A deprecation names the version it will be removed in, and that version is two minor versions ahead of the
one in ``pyproject.toml``. With ``0.10.1.dev0`` in the file, a deprecation written today names ``v0.12.0``.
Two rather than one, because the next minor version is usually close enough that a deprecation landing now
would give nobody time to act on it.

The version goes in both the ``FutureWarning`` and the changelog line, next to what to use instead:

.. code-block:: python

   warnings.warn(
       "'es_key' is deprecated and will be removed in v0.12.0. Use 'metadata_key' instead.",
       FutureWarning,
       stacklevel=2,
   )

Why a version and not a date
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A version is something a reader can act on. Told that something goes in ``v0.12.0``, they can pin
``neuroconv<0.12`` and migrate on their own schedule. Told that it goes "on or after August 2027", they have
nothing to pin against, and nothing enforces the date either, so it is as easily missed as met.

Removing it
~~~~~~~~~~~

The removal happens at the minor version the warning names, never earlier and never in a patch release.
Clearing the deprecations that have come due is a step of :ref:`making_a_release`.

Some older warnings still carry a date, worded "on or after <Month Year>". Those are triggered by their
date rather than by a version, since the date is the promise they shipped under, and they are being
restated as versions.
