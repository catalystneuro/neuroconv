## NWB Addendum for HED

When annotating a trials table, columns that represent time end in "_time" and are in seconds. HED should tag these columns with "Time-value/# s".

For example,
name: center_target_appearance_time:
description: Time when center target appeared for monkey to align cursor and initiate trial (seconds).

can be tagged with the following:

Definition: (Definition/Center-target-event, (Sensory-event, Visual-presentation, Cue, ((Target), (Center-of, Computer-screen))))

The full HED tag for this column would be: Def/Center-target-event, Time-value/# s
