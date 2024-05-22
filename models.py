import os
from pathlib import Path
import pydantic
import yaml
from execution.consts import BENCHMARK_CONFIG_PATH
from execution.consts import EXIT_ON_ERROR
from utils import is_safe_path
import rich
import rich.padding

class RuntimeSettings(pydantic.BaseModel):
    project_name: str
    benchmark_mode: bool = False
    ignore_cache: bool = False

    def load_benchmark_file(self) -> dict:
        """Load the benchmark file for the project.

        File should be located at `projects/{project_name}/benchmark.yml`

        Represents all the executions that should be run, and the user inputs for each execution (external inputs).

        Structure:
            ```yaml
                executions:
                  - user_inputs:
                    x: y
                    ...
            ```
        """
        try:
            if not is_safe_path(Path.cwd() / 'projects', Path.cwd() / 'projects' / self.project_name / BENCHMARK_CONFIG_PATH):
                if EXIT_ON_ERROR:
                    rich.print(
                        rich.padding.Padding(
                            f"[bold red]Error: Directory traversal detected in project name[/bold red]",
                            (2, 4),
                            expand=True,
                            style="bold red",
                        )
                    )
                    os._exit(1)
                else:
                    raise FileNotFoundError("Directory traversal detected in project name")
            
            with open(
                Path.cwd() / 'projects' / self.project_name / BENCHMARK_CONFIG_PATH, 'r'
            ) as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Benchmark file not found for project {self.project_name}")
