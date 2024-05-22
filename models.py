import os
from pathlib import Path

import pydantic
import yaml

from execution.consts import BENCHMARK_CONFIG_PATH


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
            with open(
                Path.cwd() / 'projects' / self.project_name / BENCHMARK_CONFIG_PATH, 'r'
            ) as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Benchmark file not found for project {self.project_name}")
