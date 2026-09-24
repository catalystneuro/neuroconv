# %%
"""Test HED tag generation with real OpenRouter API."""

import os
from pathlib import Path

# Load environment variables from .env file manually (no external dependency)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found in environment")

print(f"API key loaded: {api_key[:20]}...")

# %%
from neuroconv.tools.hed import generate_hed_tags_for_trials

# Define some example trial columns
columns = {
    "stimulus_type": "Type of visual stimulus presented (grating, natural image, or blank screen)",
    "response_time": "Time of subject button press response in seconds",
    "correct": "Whether the response was correct (True/False)",
    "trial_id": "Unique identifier for each trial",
    "contrast": "Contrast level of the visual stimulus (0.0 to 1.0)",
}

# %%
# Test without comments (uses default z-ai/glm-4.6 model)
print("Testing without comments...")
result = generate_hed_tags_for_trials(
    columns=columns,
    api_key=api_key,
    include_comments=False,
)

print(f"\nHED Version: {result['hed_version']}")
print(f"Definitions: {result['definitions']}")
print("\nColumn Tags:")
for col, tag in result["column_tags"].items():
    print(f"  {col}: {tag}")

# %%
# Test with comments for one column
print("\n\nTesting with comments...")
result_with_comments = generate_hed_tags_for_trials(
    columns={"stimulus_type": columns["stimulus_type"]},
    api_key=api_key,
    include_comments=True,
)

print(f"\nHED Version: {result_with_comments['hed_version']}")
print(f"Column Tags: {result_with_comments['column_tags']}")
print(f"Comments: {result_with_comments.get('comments', {})}")

# %%
# Test with additional context
print("\n\nTesting with additional context...")
result_with_context = generate_hed_tags_for_trials(
    columns={"stimulus_type": columns["stimulus_type"]},
    api_key=api_key,
    additional_context="This is data from a visual neuroscience experiment. Use Sensory-event and Visual-presentation tags where appropriate.",
    include_comments=True,
)

print(f"\nHED Version: {result_with_context['hed_version']}")
print(f"Column Tags: {result_with_context['column_tags']}")
print(f"Comments: {result_with_context.get('comments', {})}")
