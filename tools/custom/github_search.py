from crewai_tools import BaseTool
from github import Github, GithubException
import os
import time
import ast


class GitHubSearchTool(BaseTool):
    """A tool that searches for code snippets in a GitHub repository."""
    name: str = "GitHubSearchTool"
    description: str = (
        "You use this tool to search for code snippets in a GitHub repository. The tool uses the github rest API. If you need to search for" \
        "code in a specific file in a known path, you can use the following query: 'path:/path/to/filename search_query'."
        )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def _run(self, repo_name: str, search_query: str) -> str:
        """Use the GitHubSearchTool."""
        gh = Github(os.getenv('GITHUB_TOKEN'))
        query = f'{search_query} repo:{repo_name}'
        return self.execute_search(query=query, gh=gh)
    
    def execute_search(self, gh: Github, query: str) -> str:
        try:
            search_result = gh.search_code(query)
            code_results = []
            if search_result.totalCount > 10:
                error_message = 'Too many results. Please narrow down the search. Returning without file content.'
            for item in search_result:
                file_content = item.decoded_content.decode('utf-8')
                if item.path.endswith('.py'):
                    classes, methods = self.parse_python_code(file_content)
                else:
                    classes, methods = [], []
                code_results.append({'filename': item.path,
                                     'content': file_content if search_result.totalCount <= 10 else error_message,
                                     'classes': classes,
                                     'methods': methods})
            return str(code_results)
        except GithubException as e:
            if e.status == 403 and 'rate limit' in e.data['message'].lower():
                print("Rate limit exceeded. Handling...")
                return self.handle_rate_limit(gh=gh, query=query)
            else:
                raise

    def parse_python_code(self, code):
        tree = ast.parse(code)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        methods = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        return classes, methods

    def handle_rate_limit(self, gh: Github, query: str) -> str:
        rate_limit = gh.get_rate_limit()
        reset_time = rate_limit.core.reset
        current_time = time.time()
        sleep_time = reset_time.timestamp() - current_time + 10  # adding 10 seconds to ensure the limit is reset
        print(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
        time.sleep(sleep_time)
        print("Retrying the request...")
        return self.execute_search(query)
