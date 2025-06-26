def evaluate_condition_block(condition_block: dict, crews_results: dict) -> bool:
    """
    Evaluates a single condition block (e.g., from 'depends_on' or 'resolved_inputs.case.condition')
    against the current state of crew results.

    Args:
        condition_block (dict): The dictionary defining the condition
                                (e.g., {'crew': 'name', 'status': 'SUCCESS', 'output_contains': 'MSG'}).
        crews_results (dict): A dictionary of all previously run crew results,
                              in the format {'crew_name': {'status': 'STATUS', 'output': 'OUTPUT_STRING'}}.

    Returns:
        bool: True if the condition is met, False otherwise.
    """
    if not condition_block:
        return True # An empty condition block is always met (e.g., for default cases without a condition)

    # If a condition block exists but doesn't specify a 'crew', it might be
    # intended for other generic conditions. For now, we assume if it's meant
    # to be a crew-specific condition, 'crew' must be present.
    # If 'crew' is missing, it cannot be evaluated against crews_results, so
    # we treat it as an unmet condition unless specified otherwise (e.g., a simple 'true' condition).
    # For robust_ness, it's safer to require 'crew' for these checks.
    if 'crew' not in condition_block:
        # If no 'crew' is specified, and it's not empty, it's an unhandled condition type.
        # For now, we return False for safety or True if explicitly generic.
        # For 'resolved_inputs' cases, a missing 'crew' typically means it's not a crew-based condition,
        # but for this specific context, it's expected to be crew-based.
        # Let's default to False if 'crew' is expected but missing, to prevent unintended matches.
        # However, for the `case` conditions in `resolved_inputs`, an empty condition block
        # is just `{}`, and should be True if it's the *last* fallback before `default`.
        # The `evaluate_condition_block` from `orchestrator.py` already handled empty blocks as True.
        # So if 'crew' is not in block and it's not empty, let's treat it as not met.
        # Best to raise an error if an invalid condition structure is found here in production.
        return False # Or raise ValueError("Condition block missing 'crew' key for crew-based evaluation")


    dep_crew_name = condition_block['crew']
    result_obj = crews_results.get(dep_crew_name, {})
    crew_status = result_obj.get('status')
    crew_output_content = result_obj.get('output', '')

    # 1. Check status condition
    if 'status' in condition_block and crew_status != condition_block['status']:
        return False

    # 2. Check output_contains condition
    if 'output_contains' in condition_block:
        expected_substring = condition_block['output_contains']
        # Normalize crew output for case-insensitive and whitespace-robust comparison
        normalized_crew_output = crew_output_content.strip().upper()
        normalized_expected = expected_substring.strip().upper()
        if normalized_expected not in normalized_crew_output:
            return False

    # 3. Check output_not_contains condition
    if 'output_not_contains' in condition_block:
        not_expected_substring = condition_block['output_not_contains']
        # Normalize crew output for case-insensitive and whitespace-robust comparison
        normalized_crew_output = crew_output_content.strip().upper()
        normalized_not_expected = not_expected_substring.strip().upper()
        if normalized_not_expected in normalized_crew_output: # If it IS present, condition fails
            return False

    # If all checks passed for this condition block
    return True
