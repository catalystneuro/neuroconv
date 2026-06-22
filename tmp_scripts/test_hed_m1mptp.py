# %%
"""Test generate_hed_tags_for_trials with M1MPTP trials interface columns."""

import datetime
import json
from pathlib import Path

from neuroconv.tools.hed import generate_hed_tags_for_trials

# %%
# Extract columns from M1MPTPTrialsInterface
columns = {
    "center_target_appearance_time": "Time when center target appeared for monkey to align cursor and initiate trial (seconds)",
    "lateral_target_appearance_time": "Time when lateral target appeared signaling monkey to move from center to flexion/extension position (seconds)",
    "cursor_departure_time": "Time when cursor exited from start position after lateral target appearance. Detected by cursor position leaving start zone boundary (seconds)",
    "reward_time": "Reward delivery. The animal received a drop of juice or food for successful completion of the task (seconds)",
    "movement_type": "flexion or extension",
    "torque_perturbation_type": "direction of torque perturbation causing muscle stretch (flexion/extension/none)",
    "torque_perturbation_onset_time": "onset time of unpredictable torque impulse (0.1 Nm, 50ms) applied to manipulandum 1-2s after center target capture (seconds)",
    "derived_movement_onset_time": "onset time of target capture movement derived from kinematic analysis (seconds)",
    "derived_movement_end_time": "end time of target capture movement derived from kinematic analysis (seconds)",
    "derived_peak_velocity": "peak velocity during target capture movement derived from kinematic analysis",
    "derived_peak_velocity_time": "time of peak velocity during target capture movement derived from kinematic analysis (seconds)",
    "derived_movement_amplitude": "amplitude of target capture movement derived from kinematic analysis",
    "derived_end_position": "angular joint position at end of target capture movement (degrees)",
}

# %%
# Add context about the experiment
additional_context = """
This is a center-out reaching task with a monkey (primate) subject.
- The monkey controls a cursor via wrist movements on a manipulandum
- Each trial: center target appears -> monkey aligns cursor -> lateral target appears -> monkey moves to target -> reward
- Torque perturbations are sometimes applied as mechanical stimuli to stretch muscles
- "derived_*" columns contain kinematic measurements calculated from position/velocity data, not events
- Movement types are "flexion" or "extension" referring to wrist joint movement direction
- This is a motor control/neurophysiology experiment studying MPTP (Parkinson's disease model)
"""

# %%
# Generate HED tags with logging enabled
print("Generating HED tags for M1MPTP trials interface...")
print(f"Processing {len(columns)} columns\n")

# Log file path
log_file = Path(__file__).parent / f"hed_m1mptp_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# api_key is now automatically loaded from .env file or environment variable
result = generate_hed_tags_for_trials(
    columns=columns,
    hed_version="8.4.0",
    include_comments=True,
    additional_context=additional_context,
    log_file=log_file,
    verbose=True,
)

print(f"Log file written to: {log_file}")

# %%
# Display results
print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)
print(f"\nHED Version: {result['hed_version']}")

print(f"\n{'=' * 80}")
print("DEFINITIONS")
print("=" * 80)
if result["definitions"]:
    for i, defn in enumerate(result["definitions"], 1):
        print(f"\n{i}. {defn}")
else:
    print("\nNo definitions generated.")

print(f"\n{'=' * 80}")
print("COLUMN TAGS")
print("=" * 80)
for col_name, hed_tag in result["column_tags"].items():
    print(f"\n{col_name}:")
    print(f"  Description: {columns[col_name]}")
    print(f"  HED Tag: {hed_tag}")
    if "comments" in result and col_name in result["comments"]:
        print(f"  Comment: {result['comments'][col_name]}")

# %%
# Save results to JSON
output_path = Path(__file__).parent / "hed_m1mptp_results.json"
with open(output_path, "w") as f:
    json.dump(result, f, indent=2)
print(f"\n\nResults saved to: {output_path}")
