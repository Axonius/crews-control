import hashlib
import os
import typing
from pathlib import Path
import time
import rich
from crewai import Task, Agent, Crew
from execution.contexts import load_crew_contexts
from execution.consts import EXIT_ON_ERROR
from tools.index import get_tool
from utils import is_safe_path

class NoAgentFoundError(Exception):
    pass

class NoTaskFoundError(Exception):
    pass

class CrewRunner:
    def __init__(
        self,
        project_name: str,
        crew_name: str,
        crew_config: dict,
        user_inputs: dict,
        previous_crews_results: dict,
        llm,
        embedding_model,
        should_export_results: bool = True,
        ignore_cache: bool = False,
    ):
        self._crew_name: str = crew_name
        self._user_input: dict = user_inputs
        self._crew_config: dict = crew_config
        self._project_name: str = project_name
        self._previous_results: dict = previous_crews_results
        self._llm, self._embedding_model = llm, embedding_model
        self._crew_context: typing.Optional[dict] = None
        self._ignore_cache: bool = ignore_cache

        # evaluate paths
        for key, value in (crew_config.get('context') or {}).items():
            crew_config['context'][key] = self._evaluate_input(value)

        # load crew context
        self._crew_context: dict = load_crew_contexts(project_name, crew_config)

        # output file
        self._should_export_results: bool = should_export_results
        self._output_file: str = self._evaluate_input(self._crew_config.get('output_naming_template') or '').replace('/', '-')

        # validate results
        self._validate_results: str = self._evaluate_input(crew_config.get('validate_results') or '')

        # evaluate context inputs
        self.validate_crew_parameters()

    def validate_crew_parameters(self):
        """Validate internal parameters that crew needs from 3rd parties."""
        # validations
        if 'agents' not in self._crew_config:
            raise NoAgentFoundError('Crew config must have at least one agent.')
        if 'tasks' not in self._crew_config:
            raise NoTaskFoundError('Crew config must have at least one task.')
        # check no intersection between _crew_context and _user_input
        if set(self._crew_context.keys()) & set(self._user_input.keys()) & set(self._previous_results.keys()):
            raise ValueError('Crew context and user input must not have any intersection.')

    def _evaluate_input(self, user_input: str) -> str:
        try:
            return user_input.format(
                **(self._crew_context or {}),
                **(self._user_input or {}),
                **(self._previous_results or {})
            )
        except ValueError as e:
            raise ValueError(f'\nError evaluating input: {e}\nUser input:\n---\n{user_input}\n---\n')

    def _get_tool_id(self, scope: typing.Optional[str] = None) -> str:
        if scope is None:
            return hashlib.md5(f'{self._crew_name}{list(self._user_input.values())}'.lower().encode()).hexdigest()
        return hashlib.md5(f'{self._crew_name}{scope}{list(self._user_input.values())}'.lower().encode()).hexdigest()

    def _get_agent(self, agent_name: str, agent_scope: typing.Optional[str] = None) -> Agent:
        agent_config: dict = self._crew_config['agents'].get(agent_name)
        try:
            return Agent(
                role=self._evaluate_input(agent_config['role']),
                goal=self._evaluate_input(agent_config['goal']),
                tools=[
                    get_tool(tool, task_id=self._get_tool_id(agent_scope))
                    for tool in agent_config.get('tools') or []
                ],
                backstory=self._evaluate_input(agent_config['backstory']),
                allow_delegation=False,
                llm=self._llm,
                embedding_model=self._embedding_model,
                verbose=True,
                memory=True,
            )
        except ValueError as e:
            raise ValueError(f'Error evaluating agent: {agent_name}. Error: {e}')

    def _get_crew_tasks(self) -> list[Task]:
        return [
            Task(
                description=self._evaluate_input(task_context['description']),
                expected_output=self._evaluate_input(task_context['expected_output']),
                tools=[
                    get_tool(tool, task_id=self._get_tool_id(task_name))
                    for tool in task_context.get('tools') or []
                ],
                agent=self._get_agent(agent_name=task_context['agent'], agent_scope=task_name),
            )
            for task_name, task_context in self._crew_config['tasks'].items()
        ]

    def _generate_agents(self) -> list[Agent]:
        return [
            self._get_agent(agent_name)
            for agent_name, agent_config in list(self._crew_config.get('agents').items()) or []
        ]

    def _export_results(self, results: str):
        if self._should_export_results:
            export_path: Path = self._get_export_path()
            rich.print(
                f'[green bold]'
                f'Writing {self._crew_name} result into <{export_path}>'
                f'[/green bold]'
            )
            if not export_path.parent.exists():
                export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(results)
        else:
            rich.print(f"[green bold]Crew <{self._crew_name}> result:\n{results}\n\n[/green bold]")

    def _get_export_path(self) -> Path:
        if not is_safe_path(Path.cwd() / 'projects' / self._project_name / 'output', Path(self._output_file)):
            rich.print(f"[red bold]Error: Directory traversal detected in output file {self._output_file}[/red bold]")
            os._exit(1)

    def run_crew(self) -> str:
        export_path: Path = self._get_export_path()
        if not self._ignore_cache and export_path.exists():
            return export_path.read_text()

        max_retries = 5
        retry_count = 0
        backoff_factor = 2

        while retry_count < max_retries:
            try:
                results: str = Crew(
                    agents=self._generate_agents(),
                    tasks=self._get_crew_tasks(),
                    verbose=2
                ).kickoff()
                self._export_results(results)
                return results

            except Exception as e:
                error_code = self._extract_error_code(e)  # Implement this method to extract the error code
                if error_code == "429":  # Check for rate limit error code
                    retry_count += 1
                    wait_time = backoff_factor ** retry_count
                    rich.print(f"[yellow bold]Rate limit error encountered. Retrying in {wait_time} seconds...[/yellow bold]")
                    time.sleep(wait_time)
                else:
                    rich.print(f"[red bold]Error occurred while running crew <{self._crew_name}>[/red bold]")
                    rich.print(f"[red bold]Error: {e}[/red bold]")
                    if EXIT_ON_ERROR:
                        os._exit(1)
                    return str(e)

        rich.print(f"[red bold]Exceeded maximum retries. Aborting...[/red bold]")
        return "Rate limit error: Exceeded maximum retries"

    def _extract_error_code(self, exception: Exception) -> str:
        # Example implementation - adjust based on your actual exception structure
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            return str(exception.response.status_code)
        return ""