from crewai_tools import BaseTool
from github import Github, GithubException
import os
import time
import ast
import datetime

class GitHubSearchTool(BaseTool):
    """A tool that searches for code snippets in a GitHub repository."""
    name: str = "GitHubSearchTool"
    description: str = (
        """You use this tool to search for query terms inside of a file in a GitHub repository.
        
        The tool uses the github rest API. If you need to search for
        code in a specific file in a known path, you can use the following query: 'path:/path/to/filename search_query'.

        
        You can get text match metadata for the file content and file path fields when you pass the text-match media type.


        For example, if you want to find the definition of the addClass function, your query would look something like this:

        ```
        addClass in:file language:js
        ```

        This query searches for the keyword addClass within a file's contents. The query limits the search to files where the
        language is JavaScript in the repository.

        there are a few restrictions on how searches are performed:

        - Only the default branch is considered.
        - Only files smaller than 384 KB are searchable.
        - You *MUST ALWAYS* include at least one search term when searching source code.
          For example, searching for "language:go" is not valid, while "amazing language:go" is.
          Another example, searching for "path:/README.md" is not valid, while "amazing path:/README.md" is.

        The query contains one or more search keywords and qualifiers.
        Qualifiers allow you to limit your search to specific areas of GitHub.
        The REST API supports the same qualifiers as the web interface for GitHub. 

        A query can contain any combination of search qualifiers supported on GitHub. The format of the search query is:

        ```
        SEARCH_KEYWORD_1 SEARCH_KEYWORD_N QUALIFIER_1 QUALIFIER_N
        ```
        """
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

    def utc_to_local(self, utc_dt):
        epoch = time.mktime(utc_dt.timetuple())
        offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
        return utc_dt + offset

    def handle_rate_limit(self, gh: Github, query: str) -> str:
        current_time = time.time()
        local_reset_timestamp: datetime = time.mktime(self.utc_to_local(gh.get_rate_limit().search.reset).timetuple())
        print(f"Time until reset: {local_reset_timestamp - current_time} seconds")

        sleep_time = local_reset_timestamp - current_time + 10  # adding 10 seconds to ensure the limit is reset

        if sleep_time > 0:
            print(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time)
        else:
            print(f"Calculated negative sleep time: {sleep_time} seconds. Reset time might have already passed.")

        print("Retrying the request...")
        return self.execute_search(query)
