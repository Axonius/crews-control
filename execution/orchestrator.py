from pathlib import Path

import rich
import yaml

from execution.consts import EXECUTION_CONFIG_PATH
from execution.crews.builder import CrewRunner
from execution.graph import get_crews_execution_order
from utils import get_openai_clients
from utils import sanitize_filename
from utils import is_safe_path
import os

def execute_crews(project_name: str,
                  user_inputs: dict = None,
                  validations: dict = None,
                  ignore_cache: bool = False):
    """Execute crews in the order defined in the execution config."""
    if not user_inputs:
        user_inputs = {}

    if not is_safe_path(Path.cwd() / 'projects', Path(project_name)):
        rich.print(
            f"[bold red]Error: Path traversal detected in project name: {project_name}[/bold red]"
        )
        os._exit(1)

    execution_config: dict = get_execution_config(project_name)
    llm, embedding_model = get_openai_clients()
    execution_order: list[str] = get_crews_execution_order(execution_config)

    rich.print(
        f'[bold white]'
        f'Starting execution with the following order: {execution_order}\n'
        f'[/bold white]'
    )

    crews_results: dict = {}
    for acting_crew in execution_order:
        crew_config: dict = execution_config['crews'][acting_crew]
        rich.print(f"[white bold]Running crew <{acting_crew}> [/white bold]")
        result: str = CrewRunner(
            project_name=project_name,
            crew_name=acting_crew,
            crew_config=crew_config,
            user_inputs=user_inputs,
            previous_crews_results=crews_results,
            llm=llm,
            embedding_model=embedding_model,
            should_export_results=(execution_config.get('settings') or {}).get('output_results'),
            ignore_cache=ignore_cache,
        ).run_crew()
        crews_results[acting_crew] = result
        if validations and acting_crew in validations:
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
                    {result}
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
                verbose = 2,
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
                file.write(validation_result)


def get_execution_config(project_name: str) -> dict:
    if not is_safe_path(Path.cwd() / 'projects', Path(project_name) / EXECUTION_CONFIG_PATH):
        rich.print(
            f"[bold red]Error: Directory traversal detected in project name: {project_name} [/bold red]"
        )
        os._exit(1)

    with open(
        Path.cwd() / 'projects' / project_name / EXECUTION_CONFIG_PATH, 'r'
    ) as file:
        execution_config: dict = yaml.safe_load(file)
    return execution_config
