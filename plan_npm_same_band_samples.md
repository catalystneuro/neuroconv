# Plan: `same_band_samples` policy on `NPMFiberPhotometryInterface`

Agreed with Paul on [PR #1756](https://github.com/catalystneuro/neuroconv/pull/1756#issuecomment-5122095159)
(2026-07-29): "Leaving it up to the user to determine the policy sounds like the right way to go about
this. I am totally on board", and he leaves the implementation to us. #1756 is approved and merges
without this; the work below is a follow-up PR against main.

## The problem, for the PR description

Each frame carries a `Flags`/`LedState` word whose three lowest bits say which excitation lamps were
on. 415 nm and 470 nm both drive green-emitting indicators, so their emission passes the same filter
onto the same half of the sensor and lands in the same region columns. A frame with both lit therefore
yields **one number that is the sum of the two responses**, with no second column holding the other
half, unlike a `LedState` 6 frame where the 470 nm answer is in green and the 560 nm answer is in red.

The shipped predicate is `(value & code) == code`, so that summed number is written into the 415 nm
series *and* the 470 nm series, each declaring a single `excitation_wavelength_in_nm` on the
`FiberPhotometryTable`. There is no neutral alternative: excluding the sample is also a choice. So the
interface should stop choosing and ask.

## The change

```python
same_band_samples: Literal["include", "exclude"] | None = None
```

`None` is not a default policy, it is the absence of one. When a file contains same-band samples and
the caller has not chosen, raise. When it does not, which is every file in existence, the parameter is
never mentioned and nobody learns it exists.

### Constant

```python
# 415 nm and 470 nm emission both reach the green region columns, so a frame with both lit yields one
# number that is their sum. 560 nm reaches the red columns and never collides with either.
_SAME_BAND_CODE = {415: 2, 470: 1, 560: 0}
```

Note the trigger is "two lit lamps reach this column's emission band", not "all three lamps are on".
In a `LedState` 7 frame the red columns still have exactly one lamp arriving, so 560 nm stores
normally and only the green series are affected. That is what `_SAME_BAND_CODE[560] = 0` encodes.

### `__init__`

Slots in after `_read_state_values`, which already loads the whole state column, so there is no extra
I/O and no new file read:

```python
code = _WAVELENGTH_TO_CODE[excitation_wavelength_in_nm]
same_band_code = _SAME_BAND_CODE[excitation_wavelength_in_nm]
skip_rows, state_values = self._read_state_values(file_path, state_column, read_kwargs)

matching_states = [value for value in state_values if value & code == code]
same_band_states = [value for value in matching_states if value & same_band_code]

if same_band_states and same_band_samples is None:
    raise ValueError(...)
if same_band_samples == "exclude":
    matching_states = [value for value in matching_states if value not in same_band_states]

assert matching_states, (...)   # existing, now also covers "exclusion emptied the channel"
```

### The error message

It is the whole user-facing surface of this change, so it has to explain the choice rather than just
refuse. It should name the offending `LedState` values, say why the sample cannot be split, and give
both options with what each does.

```
'<file>' has samples where another excitation lamp in the same emission band was lit alongside
415 nm (LedState [3]). Both emissions reach the same region columns, so those samples are the sum of
two responses and cannot be separated. Choose explicitly: same_band_samples="exclude" leaves them out
of this series, same_band_samples="include" writes them as 415 nm samples.
```

### `get_available_excitation_wavelengths`

Leave it alone. It is a discovery helper rather than a writer, it has no policy argument, and
threading one through would make discovery depend on a decision the user has not made yet. Note in its
docstring that it reports what is present regardless of policy, so a wavelength it lists can still
raise at construction.

## Tests

**A synthetic fixture is required and is justified here.** No published file exercises this: across 28
Neurophotometrics files from 8 labs, roughly 3.7 million rows, `LedState` 3 never appears and 7 appears
only as the dark initialization frame at row 0. This is the one case where a synthetic input uniquely
covers a branch no acquired data can reach, rather than duplicating gin coverage.

Build it in `tmp_path` from a small alternating 415/470 table with a handful of rows rewritten to 3.

1. Same-band samples present, policy unset, raises, and the message names the state.
2. `"exclude"` drops them and the resulting series is shorter by exactly that count.
3. `"include"` keeps them and reproduces today's behaviour byte for byte.
4. Exclusion emptying a channel hits the existing `assert` rather than writing an empty series.
5. `LedState` 7 with a 560 nm request still stores normally under `"exclude"`, the regression guard for
   the band rule versus a lamp count.
6. Every existing gin fixture still constructs with the parameter unset, which is the real assurance
   that the happy path is untouched.

## Docs

Gallery page: one sentence noting the parameter exists and that it only ever appears if a file has such
samples. The class docstring already explains the band mechanics for `LedState` 6 and needs the
same-band case added alongside, since it currently only describes the separable one.

## CHANGELOG

Under Features, since it is new public API on an interface that has not shipped in a release yet.

## Open, decide during implementation

**The parameter name.** `same_band_samples` needs the band concept spelled out in the docstring to be
readable. `mixed_excitation_samples` and `compound_excitation_samples` were both rejected because they
read as covering `LedState` 6, which this must not touch. Naming it after the consequence rather than
the cause may be better and nothing good has surfaced yet.

## Held, if the thread reopens

- **The vendor's own deinterleave uses the include rule**, `source.Where(input => (input.Flags & filter) != 0)`
  (`PhotometryData.cs:27`), unchanged across their history. It does not transfer: that is a Bonsai filter
  on the live frame stream, upstream of the file, where the frame keeps its `Flags` and nothing is
  asserted. They have no CSV reader at all.
- **Precedent for raising at construction**: `timestamps_column` already fails loudly on a file carrying
  `SystemTimestamp` and `ComputerTimestamp` instead of `Timestamp`. Same shape, Paul's own design.
- **Do not volunteer** `FrameFlags.Stimulation` (bit 5), the FP3002's built-in optogenetics laser at
  450 nm or 635 nm. It is a fourth light source that can contaminate a band and that nobody, including
  IBL, treats as one. It generalises the rule, but no file has bit 5 set and raising it widens a change
  that works because it is narrow.

## Related

- Vault: `ongoing_work/fiber_photometry/npm_same_band_policy_followup.md`
- Vault: `reference/npm_compound_frame_contamination.md`, the measured cost and the slope mechanism
- Vault: `source_formats/neurophotometrics/npm_format_specification.md`, the bit layout and the survey
