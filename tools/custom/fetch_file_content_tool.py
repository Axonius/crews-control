import subprocess
from typing import Optional
from pydantic import BaseModel, validator

from crewai_tools import BaseTool
from embedchain import App

class GitFileContentQueryTool(BaseTool):
    """A tool that fetches file content from a local git repository."""
    name: str = "GitFileContentQueryTool"
    repo_path: Optional[str] = None
    description: str = (
        "This tool fetches the content of a file from a local git repository."
    )
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, repo_path: str, **kwargs):
        super().__init__(**kwargs)
        self.repo_path = repo_path

    def _run(self, file_path: str) -> str:
        """Use the GitFileContentQueryTool."""
        return self.fetch_file_from_git(file_path=file_path)

    def fetch_file_from_git(self, file_path: str) -> str:
        """
        Fetches the content of a file from a local git repository.

        Args:
            file_path (str): The path to the file within the repository.

        Returns:
            str: The content of the file as a string, or an error message if the operation fails.

        Raises:
            FileNotFoundError: If the git repository does not exist at the provided path.
            subprocess.CalledProcessError: If the git command fails.
        """
        # Construct the full path to the file in the git repository
        full_file_path = f"{self.repo_path}/{file_path}"

        # Construct the git command to show the file content
        git_command = ["git", "-C", self.repo_path, "show", f"HEAD:{file_path}"]

        try:
            # Execute the git command using subprocess
            result = subprocess.run(git_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)

            # Return the standard output which contains the file content
            return result.stdout
        except FileNotFoundError:
            # Raise an error if the git repository does not exist
            raise FileNotFoundError(f"The specified repository path does not exist: {self.repo_path}")
        except subprocess.CalledProcessError as e:
            # Return the standard error output if the git command fails
            return e.stderr

# Example usage:
# tool = GitFileContentQueryTool(repo_path='/path/to/repo')
# content = tool._run('path/to/file')
# print(content)
