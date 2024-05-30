import subprocess
from crewai_tools import BaseTool
from pathlib import Path
class GitSearchTool(BaseTool):
    """A tool that searches for a query string within a local git repository."""
    name: str = "GitSearchTool"
    description: str = (
        """
        This tool executes a git search command in a local git repository folder using the provided query string.
        The syntax for the query string is the same as the syntax for the `git grep` command.
        """
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(self, query: str, repo_path: str) -> str:
        """Use the GitSearchTool."""
        return self.git_search(query=query, repo_path=repo_path)

    def git_search(self, query: str, repo_path: str) -> str:
        """
        Executes a git search command in the local git repository folder using the provided query string.

        Parameters:
        query (str): The query string to search for in the git repository. The syntax is the same as the `git grep` command.
        repo_path (str): The path to the local git repository.

        Returns:
        str: The result of the git search command as a string.

        Raises:
        Exception: If there is an issue with executing the git search command.
        """
        try:
            # Construct the git search command
            repo_path = Path(repo_path).resolve()
            command = ['git', '-C', repo_path, 'grep', '-n', query]

            # Execute the command using subprocess
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if the command was successful
            if result.returncode == 0:
                # Return the standard output of the git command
                return result.stdout
            else:
                # Return the standard error if the command failed
                return result.stderr
        except Exception as e:
            # Return the exception message if an error occurs
            raise Exception(f"Failed to execute git search: {e}")

