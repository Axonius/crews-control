import shutil
import argparse
from pathlib import Path
from rich.console import Console
from utils import is_safe_path
import rich
import os

console = Console()

def strip_code_block(yaml_content):
    if yaml_content.startswith("```yaml") and yaml_content.endswith("```"):
        yaml_content = yaml_content[7:-3].strip()
    return yaml_content

def create_project_folder(yaml_file, project_name):
    projects_dir = Path.cwd() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    if not is_safe_path(projects_dir, Path(project_name)):
        rich.print(f"[bold red]Error: Path traversal detected in project name {project_name}[/bold red]")
        os._exit(1)

    project_folder = projects_dir / project_name
    project_folder.mkdir(exist_ok=True)

    destination_file = project_folder / "execution.yaml"

    with open(yaml_file, 'r') as file:
        yaml_content = file.read()
    
    yaml_content = strip_code_block(yaml_content)

    with open(destination_file, 'w') as file:
        file.write(yaml_content)

    console.print(f"[green]Project folder '{project_name}' created successfully.[/green]")
    console.print(f"[blue]YAML file copied to '{destination_file}'.[/blue]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a project folder and copy a YAML file to it.")
    parser.add_argument("yaml_file", type=Path, help="The path to the YAML input file.")
    parser.add_argument("project_name", type=str, help="The name of the project.")
    
    args: argparse.ArgumentParser = parser.parse_args()
    
    if not args.yaml_file.is_file():
        console.print(f"[red]Error: The file '{args.yaml_file}' does not exist.[/red]")
        exit(1)

    create_project_folder(args.yaml_file, args.project_name)
