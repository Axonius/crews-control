from crewai.tools import BaseTool
from github import Github, GithubException
import os

MAX_PAGE_LEN = 3000

class GitHubFilePaginator(BaseTool):
    """A tool that fetches file content from GitHub, splits it into pages, and returns a specified page."""
    name: str = "GitHubFilePaginator"
    description: str = (
        """
**Tool Name: GitHubFilePaginator**

**Description:**
Use this tool to fetch the content of a file from a GitHub repository, split it into pages, and return the specified page.

**Usage:**
Provide the repository name, file path, and page number (page 0 is the first page) to fetch the content of the file from
the specified page.

**Example:**
```
repo_name: "owner/repo"
file_path: "path/to/file.py"
page_number: 1
```
"""
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(self, repo_name: str, file_path: str, page_number: int) -> str:
        """Use the GitHubFilePaginator."""
        gh = Github(os.getenv('GITHUB_TOKEN'))
        return self.fetch_page_content(gh, repo_name, file_path, page_number)

    def fetch_page_content(self, gh: Github, repo_name: str, file_path: str, page_number: int) -> str:
        try:
            repo = gh.get_repo(repo_name)
            file_content = repo.get_contents(file_path).decoded_content.decode('utf-8')
            pages = self.split_into_pages(file_content)
            
            if 0 <= page_number < len(pages):
                return pages[page_number]
            else:
                return "Invalid page number. Please provide a valid page number."
        except GithubException as e:
            if e.status == 403 and 'rate limit' in e.data['message'].lower():
                return "Rate limit exceeded. Please try again later."
            else:
                return f"An error occurred: {str(e)}"

    def split_into_pages(self, content: str) -> list:
        return [content[i:i+MAX_PAGE_LEN] for i in range(0, len(content), MAX_PAGE_LEN)]
