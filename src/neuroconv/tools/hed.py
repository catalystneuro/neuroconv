"""Tool functions for generating HED (Hierarchical Event Descriptors) tags for trials table columns."""

import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .importing import get_package

# Path to the HED annotation semantics markdown file
_HED_SEMANTICS_FILE = Path(__file__).parent / "hed_annotation_semantics.md"


def _load_hed_semantics_guide() -> str:
    """Load the HED annotation semantics guide from the markdown file."""
    return _HED_SEMANTICS_FILE.read_text(encoding="utf-8")


def get_flattened_hed_schema(hed_version: str | None = None) -> dict[str, str]:
    """
    Extract HED schema tags as a flattened dictionary mapping tag paths to descriptions.

    Parameters
    ----------
    hed_version : str or None, default: None
        The version of the HED schema to use. If None, uses the latest version.

    Returns
    -------
    dict[str, str]
        A dictionary mapping full tag paths (e.g., "Event/Sensory-event") to their descriptions.

    Examples
    --------
    >>> schema = get_flattened_hed_schema()
    >>> "Event/Sensory-event" in schema
    True
    """
    hed = get_package(
        package_name="hed",
        installation_instructions="pip install hedtools",
    )

    schema = hed.schema.load_schema_version(hed_version)
    flattened = {}

    def process_tag(tag_entry: Any, parent_path: str = "") -> None:
        """Recursively process HED schema tags."""
        tag_name = tag_entry.short_tag_name
        full_path = f"{parent_path}/{tag_name}" if parent_path else tag_name
        description = tag_entry.description or ""
        flattened[full_path] = description

        # Process children
        for child in tag_entry.children.values():
            process_tag(child, full_path)

    # Process all top-level tags
    for tag_entry in schema.tags.values():
        process_tag(tag_entry)

    return flattened


def _call_openrouter_api(
    messages: list[dict[str, str]],
    api_key: str,
    model: str,
) -> str:
    """
    Call OpenRouter API with the given messages.

    Parameters
    ----------
    messages : list[dict[str, str]]
        List of message dictionaries with 'role' and 'content' keys.
    api_key : str
        OpenRouter API key.
    model : str
        Model identifier (e.g., "anthropic/claude-sonnet-4").

    Returns
    -------
    str
        The assistant's response content.

    Raises
    ------
    RuntimeError
        If the API call fails.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": messages,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else "No error body"
        raise RuntimeError(f"OpenRouter API error ({e.code}): {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling OpenRouter API: {e.reason}") from e


def _validate_hed_string(
    hed_string: str,
    hed_version: str | None = None,
    def_dicts: Any | None = None,
    definitions_allowed: bool = False,
) -> list[str]:
    """
    Validate a HED string and return list of error messages.

    Parameters
    ----------
    hed_string : str
        The HED string to validate.
    hed_version : str or None, default: None
        The version of the HED schema to use. If None, uses the latest version.
    def_dicts : DefinitionDict or list or dict or None, default: None
        Definition dictionaries to use for validating Def/ tag references.
        Required when validating strings that contain Def/ tags.
    definitions_allowed : bool, default: False
        If True, allows Definition tags in the string (for validating definition strings).
        If False, flags definitions found as errors.

    Returns
    -------
    list[str]
        List of validation error messages. Empty if valid.
    """
    # Skip validation for empty or non-string values
    if not hed_string or not isinstance(hed_string, str):
        return ["Invalid HED string: empty or not a string"]

    # Strip whitespace
    hed_string = hed_string.strip()
    if not hed_string:
        return ["Invalid HED string: empty after stripping whitespace"]

    hed = get_package(
        package_name="hed",
        installation_instructions="pip install hedtools",
    )

    schema = hed.schema.load_schema_version(hed_version)

    try:
        # Import HedValidator from the correct module path
        from hed.validator import HedValidator

        hed_string_obj = hed.models.HedString(hed_string, schema)
        # Use HedValidator with def_dicts to properly validate Def/ tag references
        validator = HedValidator(
            hed_schema=schema,
            def_dicts=def_dicts,
            definitions_allowed=definitions_allowed,
        )
        issues = validator.validate(hed_string_obj, allow_placeholders=False)
        return [str(issue) for issue in issues]
    except Exception as e:
        return [f"HED parsing error: {str(e)}"]


def _build_hed_system_prompt(
    schema_text: str,
    additional_context: str | None = None,
    include_comments: bool = False,
) -> str:
    """
    Build the system prompt for HED tag generation.

    Parameters
    ----------
    schema_text : str
        The flattened HED schema as text (tag: description format).
    additional_context : str or None, default: None
        Optional additional context to include in the prompt.
    include_comments : bool, default: False
        If True, includes instructions for generating comments.

    Returns
    -------
    str
        The complete system prompt for the LLM.
    """
    # Load the HED semantics guide from external markdown file
    hed_semantics_guide = _load_hed_semantics_guide()

    # Build the base system prompt
    system_prompt = f"""You are an expert in HED (Hierarchical Event Descriptors) for neuroscience data annotation.
Your task is to generate appropriate HED tags for ALL columns in a trials table simultaneously.

{hed_semantics_guide}

## HED Schema (tag: description format)
{schema_text}

## Core Rules
1. Columns for identifiers (trial_id, session_id) should return null
2. Group related properties together using parentheses: (Red, Circle)
3. Include both Event-type AND Task-event-role for event columns
4. Create Definitions for complex patterns that could be reused
5. Consider relationships between columns when creating tags and definitions"""

    # Add additional context if provided
    if additional_context:
        system_prompt += f"""

## Additional Context from User
{additional_context}"""

    # Add output format instructions
    if include_comments:
        system_prompt += """

## Output Format
Return a JSON object with the following structure:
{
    "definitions": ["(Definition/Name1, (tag1, tag2, ...))", ...],
    "column_tags": {
        "column_name": "HED string or null",
        ...
    },
    "comments": {
        "column_name": "Explanation of why these tags were chosen or why null",
        ...
    }
}

CRITICAL FORMAT RULE: Each value in "column_tags" MUST be either:
- A single HED string (e.g., "Sensory-event, Visual-presentation")
- null (for columns that don't represent events, like pure numeric values or categorical data without event semantics)

DO NOT return dictionaries/objects mapping values to tags. For categorical columns (e.g., "stimulus_type" with values "grating" or "natural"), return null and explain in comments that categorical value mappings are not supported.

The "comments" field should explain your reasoning for each column's tag selection."""
    else:
        system_prompt += """

## Output Format
Return a JSON object with the following structure:
{
    "definitions": ["(Definition/Name1, (tag1, tag2, ...))", ...],
    "column_tags": {
        "column_name": "HED string or null",
        ...
    }
}

CRITICAL FORMAT RULE: Each value in "column_tags" MUST be either:
- A single HED string (e.g., "Sensory-event, Visual-presentation")
- null (for columns that don't represent events, like pure numeric values or categorical data without event semantics)

DO NOT return dictionaries/objects mapping categorical values to tags. For categorical columns, return null."""

    return system_prompt


def _extract_json_from_response(response: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        json_lines = []
        in_json = False
        for line in lines:
            if line.startswith("```") and not in_json:
                in_json = True
                continue
            elif line.startswith("```") and in_json:
                break
            elif in_json:
                json_lines.append(line)
        return "\n".join(json_lines)
    return response


def generate_hed_tags_for_trials(
    columns: dict[str, str],
    api_key: str,
    model: str = "google/gemini-3-pro-preview",
    hed_version: str | None = None,
    max_iterations: int = 3,
    additional_context: str | None = None,
    include_comments: bool = False,
    log_file: str | Path | None = None,
) -> dict[str, Any]:
    """
    Generate HED tags for trials table columns using an LLM.

    This function uses OpenRouter's API to generate HED (Hierarchical Event Descriptors)
    tags for all columns in a trials table simultaneously. The generated tags are validated
    using the hedtools library, and the LLM is given feedback to fix any validation errors.

    Parameters
    ----------
    columns : dict[str, str]
        Dictionary mapping column names to their descriptions.
        Example: {"stimulus_type": "Type of visual stimulus presented (grating or natural image)"}
    api_key : str
        OpenRouter API key for accessing the LLM.
    model : str, default: "z-ai/glm-4.6"
        Model identifier to use via OpenRouter.
    hed_version : str or None, default: None
        The version of the HED schema to use for validation. If None, uses the latest version.
    max_iterations : int, default: 3
        Maximum number of attempts to fix validation errors.
    additional_context : str or None, default: None
        Optional additional context to provide to the LLM. This can include failure modes
        from previous attempts, domain-specific guidance, or any other information that
        might help the LLM generate better HED tags.
    include_comments : bool, default: False
        If True, includes a "comments" field in the output with explanations for each
        column about why certain decisions were made. Useful for supervising agents
        or for debugging.
    log_file : str or Path or None, default: None
        Path to a log file to write detailed logs of LLM outputs and validation steps
        for each iteration. If None, no logging is performed.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - "hed_version": str - The HED schema version used
        - "definitions": list[str] - List of HED definition strings for custom tags
        - "column_tags": dict[str, str | None] - Mapping of column names to HED tag strings,
          or None if the column is not applicable for HED tagging
        - "comments": dict[str, str] - (Only if include_comments=True) Mapping of column
          names to explanatory comments about the HED tag decisions

    Examples
    --------
    >>> columns = {
    ...     "stimulus_type": "Type of visual stimulus (grating or natural image)",
    ...     "response_time": "Time of subject response in seconds",
    ...     "correct": "Whether the response was correct (True/False)",
    ... }
    >>> result = generate_hed_tags_for_trials(columns, api_key="your-api-key")
    >>> print(result)
    {
        'hed_version': '8.3.0',
        'definitions': ['(Definition/Grating, (Visual-presentation, ...))'],
        'column_tags': {
            'stimulus_type': 'Sensory-event, Visual-presentation',
            'response_time': None,
            'correct': 'Agent-action, Correct-action'
        }
    }

    >>> # With logging to track all iterations
    >>> result = generate_hed_tags_for_trials(
    ...     columns, api_key="your-api-key", log_file="hed_generation.log"
    ... )

    Notes
    -----
    The function processes all columns simultaneously in a single API call, which allows
    the LLM to consider relationships between columns and create consistent definitions
    that can be reused across columns.

    The function uses HED annotation semantics guidelines to ensure generated tags follow
    best practices like proper grouping, event classification, and the reversibility principle.
    """
    hed = get_package(
        package_name="hed",
        installation_instructions="pip install hedtools",
    )

    # Initialize logging
    log_entries = []

    def log(message: str, data: Any = None) -> None:
        """Add a log entry with timestamp."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        if data is not None:
            entry["data"] = data
        log_entries.append(entry)

    def write_log() -> None:
        """Write log entries to file if log_file is specified."""
        if log_file is not None:
            log_path = Path(log_file)
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=2, default=str)

    # Load schema to get version
    schema = hed.schema.load_schema_version(hed_version)
    actual_hed_version = schema.version

    log(
        "Starting HED tag generation",
        {
            "columns": list(columns.keys()),
            "model": model,
            "hed_version": actual_hed_version,
            "max_iterations": max_iterations,
        },
    )

    # Get flattened schema for LLM context
    schema_dict = get_flattened_hed_schema(hed_version)
    schema_text = "\n".join(f"{tag}: {desc}" for tag, desc in schema_dict.items())

    # Build columns list for prompt
    columns_text = "\n".join(f"- {name}: {desc}" for name, desc in columns.items())

    # Build the system prompt using the helper function
    system_prompt = _build_hed_system_prompt(
        schema_text=schema_text,
        additional_context=additional_context,
        include_comments=include_comments,
    )

    user_prompt = f"""Generate HED tags for ALL of these trials table columns:

{columns_text}

Return a JSON object with definitions and column_tags for all columns."""

    log(
        "Built prompts",
        {
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
            "user_prompt": user_prompt,
        },
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Get initial response
    log("Calling LLM API (initial request)")
    try:
        raw_response = _call_openrouter_api(messages, api_key, model)
    except Exception as e:
        log("LLM API call failed", {"error": str(e)})
        write_log()
        raise

    log(
        "Received LLM response (initial)",
        {
            "raw_response_length": len(raw_response),
            "raw_response": raw_response,
        },
    )

    response = _extract_json_from_response(raw_response)
    log(
        "Extracted JSON from response",
        {
            "extracted_response_length": len(response),
            "extracted_response": response,
        },
    )

    # Parse the response
    try:
        parsed = json.loads(response)
        definitions = parsed.get("definitions", [])
        column_tags = parsed.get("column_tags", {})
        comments = parsed.get("comments", {}) if include_comments else {}
        log(
            "Successfully parsed initial JSON response",
            {
                "definitions_count": len(definitions),
                "column_tags_count": len(column_tags),
                "definitions": definitions,
                "column_tags": column_tags,
            },
        )
    except json.JSONDecodeError as e:
        log(
            "Failed to parse JSON response",
            {
                "error": str(e),
                "response": response,
            },
        )
        write_log()
        # If parsing fails, return empty results with error comment
        return {
            "hed_version": actual_hed_version,
            "definitions": [],
            "column_tags": {col: None for col in columns},
            **({"comments": {col: "Failed to parse LLM response" for col in columns}} if include_comments else {}),
        }

    # Convert "null" strings to None, and handle invalid dict responses
    for col in column_tags:
        tag = column_tags[col]
        if tag is None or (isinstance(tag, str) and tag.lower() == "null"):
            column_tags[col] = None
        elif isinstance(tag, dict):
            # LLM returned a dict mapping values to tags - this is not supported
            log(
                f"Column '{col}' has invalid dict response - converting to null",
                {"original_value": tag},
            )
            column_tags[col] = None
            if include_comments:
                comments[col] = (
                    f"LLM returned value mapping dict (not supported for trials table): {tag}. "
                    "Categorical value-to-tag mappings are not supported; only single HED strings are valid."
                )

    # Validate and fix tags iteratively
    for iteration in range(max_iterations):
        log(f"Starting validation iteration {iteration + 1}")

        all_valid = True
        validation_errors = {}

        # First validate definitions (with definitions_allowed=True)
        for i, definition in enumerate(definitions):
            errors = _validate_hed_string(definition, hed_version, definitions_allowed=True)
            if errors:
                all_valid = False
                validation_errors[f"definition_{i}"] = errors

        # Create DefinitionDict from validated definitions for use in column tag validation
        def_dicts = None
        if definitions and all(f"definition_{i}" not in validation_errors for i in range(len(definitions))):
            try:
                # Create a DefinitionDict from the definition strings
                def_dicts = hed.models.DefinitionDict(definitions, schema)
                log("Created DefinitionDict from definitions", {"definition_count": len(definitions)})
            except Exception as e:
                log("Failed to create DefinitionDict", {"error": str(e)})
                # If we can't create the DefinitionDict, continue without it

        # Validate each non-null column tag (with def_dicts for Def/ tag validation)
        for col, tag in column_tags.items():
            if tag is not None:
                errors = _validate_hed_string(tag, hed_version, def_dicts=def_dicts)
                if errors:
                    all_valid = False
                    validation_errors[col] = errors

        log(
            f"Validation iteration {iteration + 1} complete",
            {
                "all_valid": all_valid,
                "validation_errors": validation_errors,
                "definitions": definitions,
                "column_tags": column_tags,
            },
        )

        if all_valid:
            log("All tags validated successfully")
            break

        # Ask LLM to fix errors
        error_text = "\n".join(f"- {col}: {'; '.join(errs)}" for col, errs in validation_errors.items())
        fix_prompt = f"""The following HED strings have validation errors:
{error_text}

Please provide corrected tags using only valid tags from the schema.
Return the complete JSON response with all definitions and column_tags (not just the ones with errors)."""

        log(
            f"Requesting fix from LLM (iteration {iteration + 1})",
            {
                "fix_prompt": fix_prompt,
            },
        )

        messages.append({"role": "assistant", "content": json.dumps(parsed)})
        messages.append({"role": "user", "content": fix_prompt})

        try:
            raw_response = _call_openrouter_api(messages, api_key, model)
        except Exception as e:
            log(f"LLM API call failed (iteration {iteration + 1})", {"error": str(e)})
            write_log()
            break

        log(
            f"Received LLM response (iteration {iteration + 1})",
            {
                "raw_response_length": len(raw_response),
                "raw_response": raw_response,
            },
        )

        response = _extract_json_from_response(raw_response)

        try:
            parsed = json.loads(response)
            definitions = parsed.get("definitions", definitions)
            column_tags = parsed.get("column_tags", column_tags)
            if include_comments:
                comments = parsed.get("comments", comments)

            log(
                f"Successfully parsed JSON response (iteration {iteration + 1})",
                {
                    "definitions_count": len(definitions),
                    "column_tags_count": len(column_tags),
                    "definitions": definitions,
                    "column_tags": column_tags,
                },
            )

            # Convert "null" strings to None
            for col in column_tags:
                if column_tags[col] is None or (
                    isinstance(column_tags[col], str) and column_tags[col].lower() == "null"
                ):
                    column_tags[col] = None
        except json.JSONDecodeError as e:
            log(
                f"Failed to parse JSON response (iteration {iteration + 1})",
                {
                    "error": str(e),
                    "response": response,
                },
            )
            # Keep previous values if parsing fails
            pass

    # Ensure all requested columns are in the result
    for col in columns:
        if col not in column_tags:
            column_tags[col] = None
            if include_comments:
                comments[col] = "Column not processed by LLM"

    result = {
        "hed_version": actual_hed_version,
        "definitions": definitions,
        "column_tags": column_tags,
    }

    if include_comments:
        result["comments"] = comments

    log(
        "HED tag generation complete",
        {
            "final_result": result,
        },
    )

    # Write log file
    write_log()

    return result
