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
from utils import EnvironmentVariableNotSetError, is_safe_path

class KeyValueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, {})
        for value in values:
            key, value = value.split('=')
            getattr(namespace, self.dest)[key] = value

def parse_arguments():
    parser = argparse.ArgumentParser("crews_control")

    parser.add_argument("--project-name", help="The name of the project to run.", type=str)
    parser.add_argument("--ignore-cache", help="Ignore the cache and run all crews", action="store_true")
    parser.add_argument('--params', nargs='+', action=KeyValueAction, help='List of key=value pairs')
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list-tools", help="List available tools", action="store_true")
    group.add_argument("--list-models", help="List available models", action="store_true")
    group.add_argument("--list-projects", help="List available projects", action="store_true")
    group.add_argument("--benchmark", help="Run the project from benchmark file (`benchmark.yml`)", action="store_true")
    
    args = parser.parse_args()

    # Ensure project name is provided if not listing
    if not (args.list_tools or args.list_models or args.list_projects):
        if not args.project_name:
            parser.error("--project-name is required for execution and benchmark")

    return args

def handle_list_arguments(args):
    if args.list_tools:
        from utils import list_tools
        list_tools()
        os._exit(0)
    elif args.list_models:
        from utils import list_models
        list_models()
        os._exit(0)
    elif args.list_projects:
        from utils import list_projects
        list_projects()
        os._exit(0)

def display_error(message):
    rich.print(Padding(f"[bold red]Error: {message}[/bold red]", (2, 4), expand=True, style="bold red"))
    os._exit(1)

def display_message(message):
    rich.print(Padding(f"[bold white]{message}[/bold white]", (2, 4), expand=True, style="bold white"))

def execute_project(runtime_settings, execution_config, user_inputs=None, validations=None):
    try:
        validate_user_inputs(user_inputs=user_inputs or {}, execution_config=execution_config)
    except ValueError as e:
        display_error(str(e))
    execute_crews(
        project_name=runtime_settings.project_name,
        user_inputs=user_inputs or get_user_inputs(execution_config),
        validations=validations,
        ignore_cache=runtime_settings.ignore_cache
    )

def main():
    args = parse_arguments()
    handle_list_arguments(args)

    runtime_settings = RuntimeSettings(
        project_name=args.project_name,
        benchmark_mode=args.benchmark,
        ignore_cache=args.ignore_cache
    )

    project_path = Path.cwd() / 'projects' / runtime_settings.project_name
    if not project_path.exists():
        display_error(f"Project {runtime_settings.project_name} not found")

    try:
        execution_config = get_execution_config(project_name=runtime_settings.project_name)
    except FileNotFoundError:
        display_error(f"{EXECUTION_CONFIG_PATH} file not found for project {runtime_settings.project_name}")

    display_message(f"Welcome to {runtime_settings.project_name}™")

    try:
        if runtime_settings.benchmark_mode:
            from utils import report_success_percentage
            benchmark_settings = runtime_settings.load_benchmark_file()
            for index, execution in enumerate(benchmark_settings.get('executions') or []):
                rich.print(f"[grey]Running benchmark execution: <{index}>[/grey]")
                execute_project(runtime_settings, execution_config, execution.get('user_inputs'), execution.get('validations'))
        elif args.params:
            user_inputs = {k: v for k, v in args.params.items()}
            execute_project(runtime_settings, execution_config, user_inputs)
        else:
            # Interactive mode: get user inputs interactively
            user_inputs = get_user_inputs(execution_config)
            execute_project(runtime_settings, execution_config, user_inputs)
    except (FileNotFoundError, EnvironmentVariableNotSetError) as e:
        display_error(str(e))

    if runtime_settings.benchmark_mode:
        if not is_safe_path(Path.cwd() / 'projects', Path.cwd() / 'projects' / runtime_settings.project_name / 'validations'):
            display_error(f"Path traversal detected in project name {runtime_settings.project_name}")
        
        report_success_percentage(f"projects/{runtime_settings.project_name}/validations")

if __name__ == "__main__":
    main()
