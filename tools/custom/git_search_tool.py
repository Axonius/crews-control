import subprocess
from crewai_tools import BaseTool
from typing import Optional
import os

class GitSearchTool(BaseTool):
    """A tool that searches for a query string within a local git repository."""
    name: str = "GitSearchTool"
    repo_path: Optional[str] = None
    description: str = (
        """
        This tool executes a git search command in a local git repository folder using the provided query string.
        The syntax for the query string is the same as the syntax for the `git grep` command.
        """
    )
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, repo_path: str, **kwargs):
        super().__init__(**kwargs)
        self.repo_path = repo_path

    def _run(self, query: str) -> str:
        """Use the GitSearchTool."""
        if query.startswith('METHOD_IMPLEMENTATION: '):
            return self.get_function_implementation(function_name=query.split(': ')[1])
        return self.git_search(query=query)

    def git_search(self, query: str) -> str:
        """
        Executes a git search command in the local git repository folder using the provided query string.

        Parameters:
        query (str): The query string to search for in the git repository. The syntax is the same as the `git grep` command.
                     if you want to get a method implementation, use the method name as the query string, prefixed with the string 'METHOD_IMPLEMENTATION: '.

        Returns:
        str: The result of the git search command as a string.

        Raises:
        Exception: If there is an issue with executing the git search command.
        """
        try:
            # Construct the git search command
            command = ['git', '-C', self.repo_path, 'grep', '-n', query]

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

    def get_function_implementation(self, function_name: str) -> str:
        # Use git_search to find the function definition
        search_result = self.git_search(f'def {function_name}(')
        
        if not search_result:
            return f"Function {function_name} not found."

        # Extract file and line number
        lines = search_result.splitlines()
        first_match = lines[0]
        file_path, line_number = first_match.split(':')[:2]
        line_number = int(line_number)

        # Read the file from the line number
        file_path = os.path.join(self.repo_path, file_path)
        with open(file_path, 'r') as file:
            lines = file.readlines()

        # Extract the function implementation
        function_lines = []
        inside_function = False
        indentation = None

        for i in range(line_number - 1, len(lines)):
            line = lines[i]
            stripped_line = line.lstrip()

            if stripped_line.startswith('def ') and inside_function:
                break

            if stripped_line.startswith('def ') and not inside_function:
                inside_function = True
                indentation = len(line) - len(stripped_line)

            if inside_function:
                function_lines.append(line)

                # Check if we've reached the end of the function
                if stripped_line and len(line) - len(stripped_line) <= indentation and not stripped_line.startswith('#'):
                    break

        return ''.join(function_lines)

# Example usage:
# git_tool = GitSearchTool('/path/to/repo')
# result = git_tool.run('search_query')
# print(result)
