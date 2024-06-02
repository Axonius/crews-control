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
        
        Except with filename searches, you must always include at least one search term when searching source code.
        For example, searching for language:javascript is not valid, while amazing language:javascript is.

        At most, search results can show two fragments from the same file, but there may be more results within the file.
        You can't use the following wildcard characters as part of your search query:

        ---
        . , : ; / \\ ` ' " = * ! ? # $ & + ^ | ~ < > ( ) { } [ ] @
        ---

        The search will simply ignore these symbols.

        With the `in` qualifier you can restrict your search to the contents of the source code file, the file path, or both.
        When you omit this qualifier, only the file contents are searched.

        in:file - Only code in the file is searched. Example: "octocat in:file" matches code where "octocat" appears in the file contents.
        in:path - Only the file path is searched. Example: "octocat in:path" matches code where "octocat" appears in the file path.
        in:file,path - Code in the file and the file path is searched. Example: "octocat in:file,path" matches code where "octocat" appears in the file contents or the file path.

        You can use the `path` qualifier to search for source code that appears at a specific location in a repository.
        Use "path:/" to search for files that are located at the root level of a repository.
        Or specify a directory name or the path to a directory to search for files that are located within that directory or any of its subdirectories.

        path:/ - Search for files located at the root level of a repository. Example: "octocat filename:readme path:/" matches readme files with the word "octocat" that are located at the root level of a repository.
        path:DIRECTORY - Search for files in a specific directory or path. Example: "form path:cgi-bin language:perl" matches Perl files with the word "form" in the cgi-bin directory, or in any of its subdirectories.
        path:PATH/TO/DIRECTORY - Search for files in a specific directory or path. Example: "console path:app/public language:javascript" matches JavaScript files with the word "console" in the app/public directory, or in any of its subdirectories (even if they reside in app/public/js/form-validators).

        You can search for code based on what language it's written in. The language qualifier can be the language name or alias.

        language:LANGUAGE - Example: "element language:xml size:100" matches code with the word "element" that's marked as being XML and has exactly 100 bytes.
        language:LANGUAGE - Example: "display language:scss" matches code with the word "display," that's marked as being SCSS.

        You can use the size qualifier to search for source code based on the size of the file where the code exists.
        The size qualifier uses greater than, less than, and range qualifiers to filter results based on the byte size of the file in which the code is found.

        size:n - Example: "function size:>10000 language:python" matches code with the word "function," written in Python, in files that are larger than 10 KB.

        The filename qualifier matches code files with a certain filename. You can also find a file in a repository using the file finder.

        filename:FILENAME - Example: "filename:linguist" matches files named "linguist".
        filename:FILENAME - Example: "filename:.vimrc commands" matches .vimrc files with the word "commands."
        filename:FILENAME - Example: "filename:test_helper path:test language:ruby" matches Ruby files named test_helper within the test directory.

        The extension qualifier matches code files with a certain file extension.

        extension:EXTENSION	- Example: "form path:cgi-bin extension:pm" matches code with the word "form," under cgi-bin, with the .pm file extension.
        extension:EXTENSION	- Example: "icon size:>200000 extension:css" matches files larger than 200 KB that end in .css and have the word "icon".
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
