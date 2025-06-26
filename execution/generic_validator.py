from crewai import Agent, Task, Crew
from crewai.task import TaskOutput # Correct import for TaskOutput
from typing import Tuple, Any, Optional, Callable
import logging

# Configure a logger for this module
logger = logging.getLogger(__name__)
# To see logs from this module, you might need to configure your root logger
# For example, in your main script:
# logging.basicConfig(level=logging.INFO)


# Global variable to hold the LLM instance for the guardrail agent
# This should be set by CrewRunner or a similar orchestrator component.
_guardrail_llm_instance: Optional[Any] = None
_validation_agent_verbose_logging: bool = False # Default to False to reduce noise

def set_guardrail_llm(llm_instance: Any, verbose_logging: bool = False):
    """
    Sets the LLM instance to be used by the generic validation agent.
    This should be called once during the setup of the main orchestrator.
    Args:
        llm_instance: The language model instance (e.g., an OpenAI client configured through LiteLLM).
        verbose_logging: Whether the validation agent's internal execution should be verbose.
    """
    global _guardrail_llm_instance
    global _validation_agent_verbose_logging
    _guardrail_llm_instance = llm_instance
    _validation_agent_verbose_logging = verbose_logging
    logger.info(f"Guardrail LLM instance set. Validation agent verbose logging: {_validation_agent_verbose_logging}")

# Fixed prompt template for the generic validation agent
_GENERIC_VALIDATOR_PROMPT_TEMPLATE = """
You are a meticulous AI Output Adherence Verifier. Your role is to assess if an AI agent's output accurately and completely fulfills its assigned task based on the provided task description and expected output criteria.

Here is the information for the task you need to verify:

----------------------------------------
ORIGINAL TASK DESCRIPTION:
{main_task_description}
----------------------------------------
ORIGINAL TASK EXPECTED OUTPUT CRITERIA:
{main_task_expected_output_literal}
----------------------------------------
ACTUAL OUTPUT PRODUCED BY THE AGENT:
'''
{actual_task_output}
'''
----------------------------------------

INSTRUCTIONS FOR VERIFICATION:
1. Carefully review the 'ORIGINAL TASK DESCRIPTION' to understand the agent's objective.
2. Thoroughly analyze the 'ORIGINAL TASK EXPECTED OUTPUT CRITERIA' to understand all requirements for a successful output (e.g., format, content, key elements, tone, length, specific inclusions/exclusions).
3. Compare the 'ACTUAL OUTPUT PRODUCED BY THE AGENT' against both the description and the expected output criteria.
4. Determine if the 'ACTUAL OUTPUT' fully and accurately meets ALL specified criteria.

YOUR RESPONSE:
* If the 'ACTUAL OUTPUT' perfectly meets all criteria: Respond ONLY with the word "VALID." (Important: Only the word "VALID." nothing else. Do not add explanations or pleasantries if it's valid).
* If the 'ACTUAL OUTPUT' fails to meet one or more criteria: Respond with "INVALID." followed by a DETAILED and SPECIFIC explanation of EACH discrepancy. Clearly state what criteria were not met and how the actual output deviates. Reference specific parts of the expected output criteria if helpful.
"""

def _run_validation_crew(
    main_task_description: str,
    main_task_expected_output: str,
    actual_task_output_raw: str
) -> str:
    """
    Internal function to set up and run the validation crew.
    """
    if not _guardrail_llm_instance:
        logger.error("Guardrail LLM is not set. Cannot perform agent-based validation.")
        # Fallback: consider the output invalid if the validator can't run.
        # This is a design choice; alternatively, it could let it pass or raise an exception.
        return "INVALID. Guardrail system error: Validator LLM not configured."

    validation_agent = Agent(
        role="AI Output Adherence Verifier",
        goal="Assess if an AI agent's output accurately and completely fulfills its assigned task based on provided criteria.",
        backstory="I am an AI expert in evaluating the quality and adherence of AI-generated content against specific requirements. I am precise and detailed in my explanations for non-compliance.",
        llm=_guardrail_llm_instance,
        allow_delegation=False,
        verbose=_validation_agent_verbose_logging, # Use configured verbosity
        memory=False # Validation agent likely doesn't need memory for a single validation task
    )

    formatted_validation_prompt = _GENERIC_VALIDATOR_PROMPT_TEMPLATE.format(
        main_task_description=main_task_description,
        main_task_expected_output_literal=main_task_expected_output,
        actual_task_output=actual_task_output_raw
    )

    validation_task = Task(
        description=formatted_validation_prompt,
        expected_output="A response starting with 'VALID.' or 'INVALID.' followed by a detailed explanation for invalid outputs.",
        agent=validation_agent,
        # No tools needed for this validation agent by default
    )

    validation_crew = Crew(
        agents=[validation_agent],
        tasks=[validation_task],
        verbose=_validation_agent_verbose_logging # Use configured verbosity
    )

    logger.info("Kicking off generic validation agent crew...")
    try:
        validation_result_str = validation_crew.kickoff()
        if validation_result_str:
             logger.info(f"Validation agent crew finished. Result: {validation_result_str.raw[:200]}...") # Log snippet
        else:
            logger.warning("Validation agent crew returned an empty or None result.")
            validation_result_str = "INVALID. Validation agent returned no output."
    except Exception as e:
        logger.error(f"Exception during validation agent crew execution: {e}", exc_info=True)
        validation_result_str = f"INVALID. Exception during validation: {str(e)}"
        
    return validation_result_str.raw


def create_generic_task_validator_function(
    main_task_description_str: str,
    main_task_expected_output_str: str
) -> Callable[[TaskOutput], Tuple[bool, Any]]:
    """
    Factory function that creates the actual guardrail function for a specific task.
    This returned function will be pre-loaded (via closure) with the
    main task's description and expected output.

    Args:
        main_task_description_str: The description of the main task being validated.
        main_task_expected_output_str: The expected output criteria of the main task.

    Returns:
        A callable function suitable for CrewAI Task's `guardrail` parameter.
    """
    logger.info(f"Creating generic task validator for task with expected output: '{main_task_expected_output_str[:100]}...'")

    def validator_for_specific_task(output_from_main_task: TaskOutput) -> Tuple[bool, Any]:
        """
        The actual guardrail function that will be called by CrewAI after a task attempt.
        It uses the generic_agent_powered_validator with the specific context of the main task.
        """
        logger.info(f"Generic validator invoked for task output (first 100 chars): '{output_from_main_task.raw[:100]}...'")

        validation_result_str = _run_validation_crew(
            main_task_description=main_task_description_str,
            main_task_expected_output=main_task_expected_output_str,
            actual_task_output_raw=output_from_main_task.raw
        )

        # Process the validation agent's response
        # Ensure case-insensitivity for "VALID." and "INVALID." checks for robustness
        validation_result_upper = validation_result_str.strip().upper()

        if validation_result_upper.startswith("VALID."):
            # Check if it's *only* "VALID." or if there's extra text.
            # The prompt asks for "ONLY the word 'VALID.'", but the LLM might not always comply perfectly.
            # For now, any response starting with "VALID." is considered a pass.
            logger.info("Validation PASSED by agent.")
            # Return the original raw output of the main task
            return True, output_from_main_task.raw
        elif validation_result_upper.startswith("INVALID."):
            # Extract the reason
            failure_reason = validation_result_str.strip()[len("INVALID."):].strip()
            if not failure_reason: # If LLM just said "INVALID." without a reason
                failure_reason = "Validation agent marked output as invalid but provided no specific reason."
            logger.warning(f"Validation FAILED by agent. Reason: {failure_reason}")
            return False, f"Output did not meet criteria: {failure_reason}"
        else:
            # The validation agent did not follow the expected "VALID."/"INVALID." format.
            # This indicates an issue with the validation agent/prompt or the LLM's ability to follow instructions.
            unstructured_feedback = f"Validation agent provided an unstructured response: '{validation_result_str}'"
            logger.error(unstructured_feedback)
            # Decide on a fallback: either fail the validation or pass it with a warning.
            # Failing is safer to ensure the main agent gets a chance to retry based on this problematic feedback.
            return False, unstructured_feedback

    return validator_for_specific_task