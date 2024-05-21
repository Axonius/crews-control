from dotenv import load_dotenv
load_dotenv()

import argparse
import rich
from rich.padding import Padding
import os
from execution.inputs import get_user_inputs, validate_user_inputs
from execution.orchestrator import execute_crews, get_execution_config
from models import RuntimeSettings
from pathlib import Path
from execution.consts import EXECUTION_CONFIG_PATH
from utils import EnvironmentVariableNotSetError

def main():
    class KeyValueAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, {})
            for value in values:
                key, value = value.split('=')
                getattr(namespace, self.dest)[key] = value

    parser = argparse.ArgumentParser("crews_control")
    parser.add_argument("--project-name", required=True, help="The name of the project to run.", type=str)

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--benchmark",
        help="Run the project from benchmark file (`benchmark.yml`)",
        action="store_true",
    )
    parser.add_argument(
        "--ignore-cache",
        help="Ignore the cache and run all crews",
        action="store_true",
    )

    group.add_argument('--params', nargs='+', action=KeyValueAction,
        help='List of key=value pairs')

    args = parser.parse_args()
    runtime_settings: RuntimeSettings = RuntimeSettings(project_name=args.project_name,
                                                        benchmark_mode=args.benchmark,
                                                        ignore_cache=args.ignore_cache)
    project_path: Path = Path.cwd() / 'projects' / runtime_settings.project_name
    if project_path.exists():
        try:
            execution_config: dict = get_execution_config(project_name=runtime_settings.project_name)
        except FileNotFoundError:
            rich.print(
                Padding(
                    f"[bold red]Error: {EXECUTION_CONFIG_PATH} file not found for project {runtime_settings.project_name}[/bold red]",
                    (2, 4),
                    expand=True,
                    style="bold red",
                )
            )
            os._exit(1)
    else:
        rich.print(
            Padding(
                f"[bold red]Project {runtime_settings.project_name} not found[/bold red]",
                (2, 4),
                expand=True,
                style="bold red",
            )
        )
        os._exit(1)

    rich.print(
        Padding(
            f"[bold white]Welcome to {runtime_settings.project_name}™[/bold white]",
            (2, 4),
            expand=True,
            style="bold white",
        )
    )

    try:
        # benchmark mode
        if runtime_settings.benchmark_mode:
            from utils import report_success_percentage
            benchmark_settings: dict = runtime_settings.load_benchmark_file()
            for index, execution in enumerate(benchmark_settings.get('executions') or []):
                rich.print(f"[grey]Running benchmark execution: <{index}>[/grey]")
                user_inputs: dict = execution.get('user_inputs') or {}
                validations: dict = execution.get('validations') or {}
                validate_user_inputs(user_inputs=user_inputs,
                                    execution_config=execution_config)
                if runtime_settings.ignore_cache:
                    execute_crews(project_name=runtime_settings.project_name,
                                user_inputs=user_inputs,
                                validations=validations,
                                ignore_cache=True)
                else:
                    execute_crews(project_name=runtime_settings.project_name,
                                user_inputs=user_inputs,
                                validations=validations)
        # params mode
        elif args.params:
            user_inputs = {}
            for key, value in args.params.items():
                user_inputs[key] = value
            validate_user_inputs(user_inputs=user_inputs,
                                execution_config=execution_config)
            execute_crews(project_name=runtime_settings.project_name,
                        user_inputs=user_inputs)

        # normal mode
        else:
            execute_crews(project_name=runtime_settings.project_name,
                        user_inputs=get_user_inputs(execution_config))
    except EnvironmentVariableNotSetError as e:
        rich.print(
            Padding(
                f"[bold red]Error: {str(e)}[/bold red]",
                (2, 4),
                expand=True,
                style="bold red",
            )
        )
        os._exit(1)

    if runtime_settings.benchmark_mode:
        report_success_percentage(f"projects/{runtime_settings.project_name}/validations")

if __name__ == "__main__":
    main()
