from crewai_tools import BaseTool
from github import Github, GithubException
import os
import time
import ast
import datetime

MAX_CONTENT_LEN = 10000
SNIPPET_LEN = 1000

class GitHubSearchTool(BaseTool):
    """A tool that searches for code snippets in a GitHub repository."""
    name: str = "GitHubSearchTool"
    description: str = (
        """
**Tool Name: GitHubSearchTool**

**Description:**
Use this tool to search for specific query terms within a file in a GitHub repository. Follow these rules and examples to ensure correct usage:

1. **General Rules:**
   - Always include at least one search term when searching source code.
   - Avoid using wildcard characters: `. , : ; / \\ ` ' " = * ! ? # $ & + ^ | ~ < > ( ) { } [ ] @`.
   - Use qualifiers to refine your search:
     - **in:file** - Search within file contents. Example: `"octocat in:file"`
     - **in:path** - Search within file paths. Example: `"octocat in:path"`
     - **in:file,path** - Search within both file contents and paths. Example: `"octocat in:file,path"`

2. **Path Qualifiers:**
   - **path:/** - Search files at the root level. Example: `"octocat filename:readme path:/"`
   - **path:DIRECTORY** - Search files in a specific directory. Example: `"form path:cgi-bin language:perl"`
   - **path:PATH/TO/DIRECTORY** - Search files in a specific directory and its subdirectories. Example: `"console path:app/public language:javascript"`

3. **Language Qualifiers:**
   - Specify the language to refine your search. Example: `"element language:xml"`

4. **Size Qualifiers:**
   - Filter results based on file size. Example: `"function size:>10000 language:python"`

5. **Filename Qualifiers:**
   - Search for files with a specific name. Example: `"filename:linguist"`
   - Combine with path and language qualifiers. Example: `"filename:test_helper path:test language:ruby"`

6. **Extension Qualifiers:**
   - Search for files with a specific extension. Example: `"icon size:>200000 extension:css"`

**Examples:**
- **Simple Search:** `"COPY filename:Dockerfile repo:Axonius/crews-control"`
- **Complex Search:** `"COPY in:file filename:Dockerfile path:/src repo:Axonius/crews-control"`

**Error Handling:**
- If you encounter a query parsing error (422), check for disallowed special characters and ensure the query includes at least one valid search term.
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
                    if item.path.endswith('.py'):
                        classes, methods = self.parse_python_code('')
                    else:
                        classes, methods = [], []
                    code_results.append({
                        'filename': item.path,
                        'content': error_message,
                        'classes': classes,
                        'methods': methods
                    })
            else:
                for item in search_result:
                    file_content = item.decoded_content.decode('utf-8')
                    if item.path.endswith('.py'):
                        classes, methods = self.parse_python_code(file_content)
                    else:
                        classes, methods = [], []

                    if len(file_content) <= MAX_CONTENT_LEN:
                        content = file_content
                    else:
                        if search_result.totalCount > 1:
                            content = 'file content too large - narrow search to this file only!'
                        else:
                            content = file_content[:SNIPPET_LEN] + '\n\n...content too large - showing snippet only.'

                    code_results.append({
                        'filename': item.path,
                        'content': content,
                        'classes': classes,
                        'methods': methods
                    })
            
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
