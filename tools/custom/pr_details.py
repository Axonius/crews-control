from typing import Type, Any
from pydantic.v1 import BaseModel, Field
from crewai_tools import BaseTool
from github import Github
import requests
import os

class GitHubPRDetailsSchema(BaseModel):
    """Input schema for GitHub PR Details Fetch Tool."""
    gh_repo: str = Field(..., description="Full name of the repository (e.g., 'user/repo')")
    pr_number: int = Field(..., description="Number of the pull request")

class GitHubPRDetailsTool(BaseTool):
    name: str = "Fetch GitHub PR Details"
    description: str = "A tool that fetches details of a specific pull request from GitHub."
    args_schema: Type[BaseModel] = GitHubPRDetailsSchema
    gh_repo: str = "default/repo"  # Default GitHub repository
    pr_number: int = 1             # Default PR number

    def _run(self, **kwargs: Any) -> Any:
        # Fetching GitHub repository and PR number from the provided arguments or defaults
        gh_repo = kwargs.get('gh_repo', self.gh_repo)
        pr_number = kwargs.get('pr_number', self.pr_number)

        # Initializing GitHub client with an environment variable token
        gh = Github(os.getenv('GITHUB_TOKEN'))
        
        # Getting the repository and pull request
        repo = gh.get_repo(gh_repo)
        pr = repo.get_pull(pr_number)

        # Headers for the request to fetch diff content
        headers = {
            'Authorization': f'Bearer {os.getenv('GITHUB_TOKEN')}',
            'Accept': 'application/vnd.github.diff'  # Media type for diff content
        }

        # Making a GET request to the diff_url with the necessary headers
        diff_response = requests.get(f'https://api.github.com/repos/{gh_repo}/pulls/{pr_number}.diff',
                                     headers=headers)

        if diff_response.status_code == 200:
            diff_content = diff_response.text
        else:
            diff_content = f"Failed to fetch diff: HTTP {diff_response.status_code} - {diff_response.reason}"

        # Constructing the details of the pull request
        pr_details = {
            'title': pr.title,
            'description': pr.body,
            'diff_url': pr.diff_url,
            'diff_content': diff_content,
            'comments': [{'user': comment.user.login, 'body': comment.body} for comment in pr.get_issue_comments()],
            'review_comments': [{'user': comment.user.login, 'body': comment.body} for comment in pr.get_review_comments()]
        }

        return pr_details
