from pathlib import Path

import rich
import yaml

from execution.consts import EXECUTION_CONFIG_PATH
from execution.crews.builder import CrewRunner
from execution.graph import get_crews_execution_order
from utils import get_openai_clients
import os


def execute_crews(project_name: str,
                  user_inputs: dict = None,
                  validations: dict = None,
                  ignore_cache: bool = False):
    """Execute crews in the order defined in the execution config."""
    if not user_inputs:
        user_inputs = {}

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
            compare_to_filename = Path(
                os.path.join(os.path.dirname(__file__),
                             f'../projects/{project_name}/validations/{validations[acting_crew]['compare_to']}')
            )
            if os.path.exists(compare_to_filename):                
                with open(compare_to_filename, 'r') as file:
                    compare_to = file.read()
                validation_results_filename = Path(
                    os.path.join(os.path.dirname(__file__),
                        f'../projects/{project_name}/validations/{validations[acting_crew]['compare_to']}.result')
                    )
            else:
                compare_to = validations[acting_crew]['compare_to']
                validation_results_filename = Path(
                    os.path.join(os.path.dirname(__file__),
                        f'../projects/{project_name}/validations/{"-".
                                                                  join(user_inputs.values()).
                                                                  replace("*","-").
                                                                  replace("/","-").
                                                                  replace("\\","-").
                                                                  replace(".","-").
                                                                  lower()}.result')
                    )

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
                    {compare_to}
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
            with open(validation_results_filename, 'w') as file:
                file.write(validation_result)


def get_execution_config(project_name: str) -> dict:
    with open(
        Path(
            os.path.join(
                os.path.dirname(__file__),
                f'../projects/{project_name}/{EXECUTION_CONFIG_PATH}'
            )
        ), 'r'
    ) as file:
        execution_config: dict = yaml.safe_load(file)
    return execution_config
