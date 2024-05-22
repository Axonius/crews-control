import abc
import os
from pathlib import Path
from utils import is_safe_path
import rich

CONTEXT_DIRECTORY_PATH = 'context'


class IFileReader(abc.ABC):
    @abc.abstractmethod
    def read(self, context_name: str, project_name: str) -> str:
        pass


class ContextFileReader(IFileReader):
    def __init__(self, context_directory_path: str = CONTEXT_DIRECTORY_PATH):
        self.context_directory_path = context_directory_path

    def read(self, context_name: str, project_name: str) -> str:
        if not context_name:
            raise ValueError('context name is required.')

        if not is_safe_path(Path.cwd() / 'projects', Path(project_name)):
            rich.print(f"[red bold]Error: Directory traversal detected in project name {project_name}[/red bold]")
            os._exit(1)

        path = Path.cwd() / 'projects' / project_name / self.context_directory_path
        if not path.exists():
            raise FileNotFoundError(f'Context directory not found at {path}.')
        return (path / context_name).read_text()


def load_crew_contexts(
    project_name: str,
    crew_config: dict,
    context_reader: IFileReader = ContextFileReader()
) -> dict[str, str]:
    """Load the contexts of all crews."""
    context: dict[str, str] = {}
    for context_name, context_file in (crew_config.get('context') or {}).items():
        context[context_name] = context_reader.read(context_file, project_name)
    return context
