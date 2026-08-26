# SLEAP: the human's corrections are dropped, and the samples after them are misdated

## What is wrong

`SLEAPInterface._get_keypoint_data` (`src/neuroconv/datainterfaces/behavior/sleap/sleapdatainterface.py:250-268`)
iterates `labeled_frame.predicted_instances` only. A proofread `.slp` holds the network's
`PredictedInstance` objects and, wherever a human fixed a frame in the GUI, a plain `Instance`
alongside or in place of one. Those are skipped.

That is the known half, recorded in `pose/pose_preexisting_defects_todo`. The half found on 2026-08-26
while writing this plan is that the frame list and the data disagree, because they read different
fields:

* `_get_labeled_frames` (`sleapdatainterface.py:~200`) keeps a frame when **any** of
  `labeled_frame.instances` belongs to this track, and `instances` includes user instances.
* `_get_keypoint_data` builds one row per frame from `predicted_instances` only.

So a frame whose only instance for this track is a human correction contributes a timestamp and no row.

## Reproduction, verified on `main` at 2026-08-26

Three frames, one track, the middle one corrected by a human:

```python
import numpy as np, sleap_io, tempfile
from pathlib import Path
from neuroconv.datainterfaces import SLEAPInterface
from pynwb.testing.mock.file import mock_NWBFile

skeleton = sleap_io.Skeleton(["head", "tail"])
track = sleap_io.Track(name="track_0")
video = sleap_io.Video(filename="recording.mp4")
frames = []
for frame_index in range(3):
    if frame_index == 1:
        instance = sleap_io.Instance.from_numpy(
            points_data=np.array([[10.0, 10.0], [11.0, 11.0]]), skeleton=skeleton, track=track
        )
    else:
        instance = sleap_io.PredictedInstance.from_numpy(
            points_data=np.array([[float(frame_index), 1.0], [2.0, 3.0]]),
            point_scores=np.array([0.9, 0.8]), score=0.9, skeleton=skeleton, track=track,
        )
    frames.append(sleap_io.LabeledFrame(video=video, frame_idx=frame_index, instances=[instance]))

path = Path(tempfile.mkdtemp()) / "proofread.slp"
sleap_io.save_slp(
    sleap_io.Labels(labeled_frames=frames, videos=[video], skeletons=[skeleton], tracks=[track]), str(path)
)

interface = SLEAPInterface(file_path=str(path), track_name="track_0", frames_per_second=1.0)
print(interface.get_timestamps())          # [0. 1. 2.]  -> three frames
nwbfile = mock_NWBFile()
interface.add_to_nwbfile(nwbfile)
series = nwbfile.processing["behavior"]["PoseEstimationTrack0"].pose_estimation_series["PoseEstimationSeriesHead"]
print(np.asarray(series.data), series.rate, series.starting_time)
```

Output: `[[0. 1.] [2. 1.]] 1.0 0.0`.

Two rows for three frames, and because the timestamps were regular the writer turned them into
`rate=1.0, starting_time=0.0`. The file therefore says the second sample was taken at t=1, when it is
frame 2 at t=2. **Every sample after a correction is written with the wrong time**, and no warning is
raised. With irregular timestamps the failure changes shape: a data array shorter than the timestamps
vector, which may or may not be caught downstream.

This settles the open question on the priorities note. It is not "missing capability, faithfully
labelled". It is wrong output in released code, so slot 1 stands on criterion 1 without the qualifier.

## What has to be decided before writing code

1. **The merge rule for a frame holding both kinds for one track.** The correction should win. State it
   and test it rather than assuming it, and check whether a user instance can carry `from_predicted`
   (the `sleap_io` field linking it back to what it replaced), which would make the pairing explicit
   instead of positional.
2. **What confidence value stands in for a human-placed point.** This is forced by our own shape:
   `_get_keypoint_data` returns `(positions, confidence)` per keypoint, with confidence an array over
   frames, so a mixed series needs a value in every row. `Instance.numpy` has no `scores` argument at
   all (signature is `(invisible_as_nan=True)`), because a human-placed point has no score. `NaN` is
   the honest filler and `confidence_definition` can say what it means. `1.0` would read as a
   confident prediction, which is exactly the thing the file should not claim.
3. **Whether the file marks a corrected point at all.** Check `ndx-pose` and the wider ecosystem for a
   convention before inventing one. If none exists, `confidence_definition` carrying the sentence is
   the cheapest honest answer, and it is already a per-series metadata field.

## The fixture

**Not blocked on data.** Neither `.slp` in `behavior_testing_data` has a single user instance, verified
on 2026-08-26: `melanogaster_courtship.slp` has 0 user and 2199 predicted, and
`predictions_1.2.7_provenance_and_tracking.slp` has 0 user and 201 predicted.

Build one instead, which is the pattern this suite already uses:
`TestSLEAPMultipleVideos._write_two_video_file` in `tests/test_on_data/behavior/test_pose_estimation_interfaces.py:325`
writes a `.slp` with `sleap_io` into `tmp_path` for exactly this reason. `sleap_io.Instance.from_numpy`
takes `points_data`, `skeleton`, `track` and `from_predicted`, so every case below is constructible.

## Implementation sketch

In `_get_keypoint_data`, iterate the frame's instances for this track rather than its predicted
instances, preferring a user instance where both are present. `Instance.numpy()` returns
`(num_nodes, 2)` and `PredictedInstance.numpy(scores=True)` returns `(num_nodes, 3)`, so the two need
squaring up to a common `(num_nodes, 3)` before the `np.stack`, with the decided filler in column 3.

Then make the two readers agree. Either `_get_labeled_frames` and `_get_keypoint_data` share one
selection helper, or a length assertion runs before the stack so a future divergence fails loudly
instead of shifting the times.

## Tests

Three cases, all on built files:

1. A frame with a correction and no prediction. Today it drops a row and shifts the rest; assert the
   row count equals the frame count and the times line up.
2. A frame with both kinds for one track. Assert the correction's coordinates are what is written.
3. A file with no user instances at all. Assert the output is byte-identical to today's, so the
   existing on-data expectations do not move.

Worth adding a fourth if the confidence decision lands on `NaN`: assert the corrected row's confidence
is `NaN` and the predicted rows keep their scores.

## Changelog

A bug-fix entry, and it should say the times were wrong rather than only that corrections were
dropped, since that is the part that changes what a user does about files they already converted.
