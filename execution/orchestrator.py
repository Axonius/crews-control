from pathlib import Path

import rich
import yaml
from typing import Union
from crewai.crews.crew_output import CrewOutput
from execution.condition_evaluator import evaluate_condition_block

from execution.consts import EXECUTION_CONFIG_PATH
from execution.crews.builder import CrewRunner
from execution.graph import get_crews_execution_order
from utils import get_clients
from utils import sanitize_filename
from utils import is_safe_path
import os
from utils import validate_env_vars
validate_env_vars('LLM_NAME', 'EMBEDDER_NAME')

def _evaluate_dependency_conditions(dependency_block: any, crews_results: dict) -> bool:
    """
    Recursively evaluates the dependency conditions based on a structured result object.
    This function handles logical operators (and, or) by recursively calling itself,
    and delegates single-crew condition evaluation to evaluate_condition_block from condition_evaluator.
    """
    if not dependency_block:
        return True

    # Base Case 1: A single string dependency (for backward compatibility: e.g., "crew_name")
    # This implicitly means the crew must have succeeded.
    if isinstance(dependency_block, str):
        return evaluate_condition_block({'crew': dependency_block, 'status': 'SUCCESS'}, crews_results)

    if isinstance(dependency_block, dict):
        # Case 2: A single crew with an optional condition (e.g., {'crew': 'name', 'condition': {...}})
        if 'crew' in dependency_block:
            # Combine the base 'crew' with its optional 'condition' block
            combined_condition = {'crew': dependency_block['crew']}
            combined_condition.update(dependency_block.get('condition', {})) # Add explicit conditions
            return evaluate_condition_block(combined_condition, crews_results)

        # Recursive Step: A logical operator block (e.g., 'and' or 'or')
        if 'and' in dependency_block:
            # All operands in the 'and' list must evaluate to True
            return all(_evaluate_dependency_conditions(op, crews_results) for op in dependency_block['and'])

        if 'or' in dependency_block:
            # At least one operand in the 'or' list must evaluate to True
            return any(_evaluate_dependency_conditions(op, crews_results) for op in dependency_block['or'])

    if isinstance(dependency_block, list): # Backward compatibility for old list format (implicit AND)
        # All items in the list must evaluate to True
        return all(_evaluate_dependency_conditions(op, crews_results) for op in dependency_block)

    # Should not reach here if the dependency structure is valid and adheres to expected formats.
    # Return False for safety if an unhandled structure is encountered.
    return False

def execute_crews(project_name: str,
                  user_inputs: dict = None,
                  validations: dict = None,
                  ignore_cache: bool = False):
    """Execute crews in the order defined in the execution config."""
    if not user_inputs:
        user_inputs = {}

    if not is_safe_path(Path.cwd() / 'projects', Path.cwd() / 'projects' / project_name):
        rich.print(
            f"[bold red]Error: Path traversal detected in project name: {project_name}[/bold red]"
        )
        os._exit(1)

    execution_config: dict = get_execution_config(project_name)
    llm_name: str = os.getenv('LLM_NAME')
    embedder_name: str = os.getenv('EMBEDDER_NAME')
    llm, embedding_model = get_clients(llm_name, embedder_name)
    execution_order: list[str] = get_crews_execution_order(execution_config)

    rich.print(
        f'[bold white]'
        f'Starting execution with the following order: {execution_order}\n'
        f'[/bold white]'
    )

    crews_results: dict = {}
    for acting_crew in execution_order:
        crew_config: dict = execution_config['crews'][acting_crew]
        dependencies = crew_config.get('depends_on')

        if dependencies:
            should_run = _evaluate_dependency_conditions(dependencies, crews_results)
            if not should_run:
                rich.print(f"[yellow bold]Skipping crew <{acting_crew}> due to unmet dependency conditions.[/yellow bold]")
                # Populate the structured result for the skipped crew
                crews_results[acting_crew] = {
                    "status": "SKIPPED",
                    "output": f"Execution skipped because dependency conditions for crew '{acting_crew}' were not met."
                }
                continue

        # Check if the crew should be run as an iterator
        if 'for_each' in crew_config:
            rich.print(f"[cyan bold]Executing iterator crew <{acting_crew}>[/cyan bold]")
            
            list_source_template = crew_config['for_each']
            
            # Build the context for formatting from previous results and user inputs
            formatting_context = {
                crew_name: result.get('output', '')
                for crew_name, result in crews_results.items()
            }
            formatting_context.update(user_inputs)

            try:
                # Evaluate the template to get the final string, then parse as JSON
                evaluated_list_string = list_source_template.format(**formatting_context)
                items_to_iterate = json.loads(evaluated_list_string)

                if not isinstance(items_to_iterate, list):
                    raise TypeError("The evaluated 'for_each' template must result in a JSON list.")

            except (json.JSONDecodeError, TypeError, KeyError) as e:
                error_msg = f"Failed to resolve 'for_each' for crew <{acting_crew}>. The template or source output was invalid. Error: {e}"
                rich.print(f"[bold red]{error_msg}[/bold red]")
                crews_results[acting_crew] = {"status": "FAILED", "output": error_msg}
                continue

            iteration_results = []
            for index, item in enumerate(items_to_iterate):
                rich.print(f"[cyan]  - Running iteration {index + 1}/{len(items_to_iterate)} for <{acting_crew}>[/cyan]")
                
                # Inject the current item into the inputs for this specific run
                iteration_user_inputs = user_inputs.copy()
                iteration_user_inputs['item'] = item
                
                # The iterator crew runs its own definition for each item
                try:
                    result: Union[CrewOutput, str] = CrewRunner(
                        project_name=project_name,
                        crew_name=f"{acting_crew}_iteration_{index}", # Dynamic name for caching
                        crew_config=crew_config, # Use its own config
                        user_inputs=iteration_user_inputs,
                        previous_crews_results=crews_results,
                        llm=llm,
                        embedding_model=embedding_model,
                        should_export_results=(execution_config.get('settings') or {}).get('output_results'),
                        ignore_cache=ignore_cache,
                    ).run_crew()
                    iteration_results.append(result)
                except Exception as e:
                    error_msg = f"Error in iteration {index} for crew <{acting_crew}>: {e}"
                    rich.print(f"[bold red]{error_msg}[/bold red]")
                    iteration_results.append({"error": error_msg})

            # Aggregate all iteration results into the output for the main iterator crew
            crews_results[acting_crew] = {"status": "SUCCESS", "output": json.dumps(iteration_results, indent=2)}
        
        else:
            # running a standard, non-iterating crew
            rich.print(f"[white bold]Running crew <{acting_crew}> [/white bold]")
            try:
                crew_run_raw_or_obj_result: Union[CrewOutput, str] = CrewRunner(
                    project_name=project_name,
                    crew_name=acting_crew,
                    crew_config=crew_config,
                    user_inputs=user_inputs,
                    previous_crews_results=crews_results, # Pass the full structured results
                    llm=llm,
                    embedding_model=embedding_model,
                    should_export_results=(execution_config.get('settings') or {}).get('output_results'),
                    ignore_cache=ignore_cache,
                    guardrail_verbose_logging=True,
    
                ).run_crew()
                if isinstance(crew_run_raw_or_obj_result, CrewOutput):
                    # If it's a CrewOutput object, get its raw string content
                    result_output: str = crew_run_raw_or_obj_result.raw
                else:
                    # Otherwise, it's already a string (from cache, or an error message string)
                    result_output: str = str(crew_run_raw_or_obj_result) # Ensure it's a string just in case
                # Wrap the successful result in the new structure
                crews_results[acting_crew] = {
                    "status": "SUCCESS",
                    "output": result_output
                }
    
            except Exception as e:
                # Handle unexpected failures during crew execution
                rich.print(f"[bold red]An unexpected error occurred while running crew <{acting_crew}>: {e}[/bold red]")
                crews_results[acting_crew] = {
                    "status": "FAILED",
                    "output": str(e)
                }
                if os.getenv('EXIT_ON_ERROR', 'False').lower() == 'true':
                    os._exit(1)

        if validations and acting_crew in validations:
            # First, ensure the crew we want to validate was actually successful
            crew_result_obj = crews_results.get(acting_crew, {})
            if crew_result_obj.get('status') != 'SUCCESS':
                rich.print(
                    f"[yellow]Skipping validation for crew <{acting_crew}> because its status was '{crew_result_obj.get('status', 'UNKNOWN')}'.[/yellow]"
                )
                continue  # Continue to the next crew in the execution order
            # It was successful, so proceed with validation.
            # IMPORTANT: The 'result' used below must be the raw output string.
            result_for_validation = crew_result_obj['output']

            from crewai import Task, Agent, Crew
            import textwrap
            validations_compare_to = validations[acting_crew]['compare_to']
            compare_to_filename: Path = (
                Path.cwd()
                / 'projects'
                / project_name
                / 'validations'
                / validations_compare_to
            )
            if compare_to_filename.exists():
                if is_safe_path(Path.cwd() / 'projects' / project_name, compare_to_filename):
                    with open(compare_to_filename, 'r') as file:
                        # validations_compare_to is a filename, overwrite var with its content to be used below
                        validations_compare_to = file.read()
                    validation_results_filename: Path = Path(f'{compare_to_filename}.result') # no need to sanitize filename or check path traversal as just adding an extension to validated path.
                else:
                    rich.print(
                        f"[bold red]Error: Path traversal detected in {compare_to_filename}[/bold red]"
                    )
                    os._exit(1)
            else:
                input_values_filename = f'{sanitize_filename("_".join(user_inputs.values()))}.result'
                validation_results_filename: Path = Path(
                    Path.cwd()
                    / 'projects'
                    / project_name
                    / 'validations'
                    / input_values_filename
                )
                if not is_safe_path(Path.cwd() / 'projects' / project_name, validation_results_filename):
                    rich.print(
                        f"[bold red]Error: Path traversal detected in {validation_results_filename}[/bold red]"
                    )
                    os._exit(1)
            
            metrics = validations[acting_crew]['metrics']

            agent = Agent(
                role = 'Software QA Engineer',
                goal = 'Validate the results of the crew',
                backstory = """You are a Software QA Engineer who is responsible for validating the results of the crew.""",
                tools = [],
                llm = llm,
            )
            task =Task(
                description = textwrap.dedent(f"""\
                    IMPORTANT INSTRUCTIONS:
                    -----------------------
                    - output MUST be in json format without any additional text (output is used by other tools - !!!NOT ENCLOSED IN JSON CODE BLOCK!!!).
                    - output MUST contain a boolean result for each check.
                    - output MUST NOT include any text other than the json object!!

                    for each of the following checks:
                    <<<<METRICS_START_MARKER>>>>
                    {metrics}
                    <<<<METRICS_END_MARKER>>>>
                    compare the result with the expected output and indicate for each check if it succeeded or not.

                    <<<<RESULT_START_MARKER>>>>
                    {result_for_validation}
                    <<<<RESULT_END_MARKER>>>>

                    <<<<EXPECTED_OUTPUT_START_MARKER>>>>
                    {validations_compare_to}
                    <<<<EXPECTED_OUTPUT_END_MARKER>>>>
                """),
                expected_output = textwrap.dedent(
                    f"""direct json string (not enclosed in json code-block) with the following structure (
                        failure requires reason, success does not):
                        -----------------------
                        {{check_endpoint: {{res: false, reason: "the version of the API endpoint URL. The result uses `/v3/admin/users/` while the expected output uses `/v2/admin/users/`"}}, check_something_else: {{res: false, reason: 'succinct reason for failue'}}, check_another_thing: {{res: true}}...}}
                        -----------------------
                        
                        IMPORTANT INSTRUCTIONS:
                        -----------------------
                        - Your response MUST be in json format without any additional text (output is used by other tools - !!!NOT ENCLOSED IN JSON CODE BLOCK!!!).
                        - Example response is the text above enclosed between horizontal lines (without the lines).
                        - Ensure the output is a direct json string (not enclosed in json code-block).
                        - Ensure there is no text before or after the json object.
                        - You MUST provide comparison reason for each failed check - i.e., what is the difference between the actual and expected output for the specific check.
                        - Reason MUST be succinct and clear.
                        """),
                tools = [],
                agent = agent,
            )
            crew = Crew(
                agents = [agent],
                tasks = [task],
                verbose = True,
            )
            validation_result = crew.kickoff()
            if not validation_results_filename.parent.exists():
                validation_results_filename.parent.mkdir(parents=True)

            if not is_safe_path(Path.cwd() / 'projects' / project_name, validation_results_filename):
                rich.print(
                    f"[bold red]Error: Path traversal detected in {validation_results_filename}[/bold red]"
                )
                os._exit(1)

            with open(validation_results_filename, 'w') as file:
                file.write(validation_result.raw)


def get_execution_config(project_name: str) -> dict:
    if not is_safe_path(Path.cwd() / 'projects', Path.cwd() / 'projects' / project_name / EXECUTION_CONFIG_PATH):
        rich.print(
            f"[bold red]Error: Directory traversal detected in project name: {project_name} [/bold red]"
        )
        os._exit(1)

    with open(
        Path.cwd() / 'projects' / project_name / EXECUTION_CONFIG_PATH, 'r'
    ) as file:
        execution_config: dict = yaml.safe_load(file)
    return execution_config
