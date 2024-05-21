import typing
import os

EXECUTION_CONFIG_PATH: typing.Final[str] = "execution.yaml"
BENCHMARK_CONFIG_PATH: typing.Final[str] = "benchmark.yaml"
OUTPUT_DIRECTORY_PATH: str = 'output'
EXIT_ON_ERROR = os.getenv('EXIT_ON_ERROR', 'False').lower() == 'true'
