from typing import Type, Any
from crewai_tools import BaseTool
from pydantic.v1 import BaseModel, Field
from github import Github, Repository
import os
import ast

class FindMethodImplementationSchema(BaseModel):
    """Input schema for Find Method Implementation Tool."""
    repo_name: str = Field(..., description="Full name of the repository (e.g., 'user/repo')")
    initial_class_name: str = Field(..., description="Initial class name to start the search from")
    method_name: str = Field(..., description="Method name to search for")
    branch: str = Field(default='main', description="Branch to search in")

class FindMethodImplementationTool(BaseTool):
    name: str = "Find Method Implementation Tool"
    description: str = "A tool that searches for the actual implementation of a method in a class hierarchy."
    args_schema: Type[BaseModel] = FindMethodImplementationSchema

    def _run(self, **kwargs: Any) -> Any:
        repo_name = kwargs.get('repo_name')
        initial_class_name = kwargs.get('initial_class_name')
        method_name = kwargs.get('method_name')
        branch = kwargs.get('branch', 'main')

        gh = Github(os.getenv('GITHUB_TOKEN'))
        repo = gh.get_repo(repo_name)
        result = self.find(github=gh,
                           repo=repo,
                           initial_class_name=initial_class_name,
                           method_name=method_name,
                           branch=branch)
        return result

    def find(self,
             github: Github,
             repo: Repository,
             initial_class_name: str,
             method_name: str,
             branch: str='main') -> str:
        """
        Recursively search for the actual implementation of a method in a class hierarchy using AST
        and returns a formatted string containing both the method source and class name.
        """
        current_class_name = initial_class_name

        while current_class_name:
            class_node, class_content, file_path = fetch_class_definition(github=github,
                                                                          repo=repo,
                                                                          class_name=current_class_name,
                                                                          branch=branch)
            if class_node:
                for node in ast.iter_child_nodes(class_node):
                    if isinstance(node, ast.FunctionDef) and node.name == method_name:
                        source = ast.get_source_segment(class_content, node)
                        return f"Method implementation found in class `{current_class_name}` in file `{file_path}`:\n" \
                               f"------------------\n" \
                               f"{source}\n" \
                               f"------------------"
                # Navigate to parent class if method not found
                for base in class_node.bases:
                    if isinstance(base, ast.Name):
                        current_class_name = base.id
                        break
                else:
                    break  # No valid parent class to search in
            else:
                break
        return f"Method implementation not found in any class derived from {initial_class_name}."

# The following functions are used by the tool and should be included in the same module.

def find_class_file(github: Github, repo: Repository, class_name: str, branch: str='main'):
    """
    Search for a file containing the specified class definition using GitHub's search API.
    
    :param repo: Repository object.
    :param class_name: Class name to search for.
    :param branch: Branch name to fetch from.
    :return: File path containing the class definition, or None if not found.
    """
    query = f'repo:{repo.full_name} "class {class_name}(" language:python'
    results = github.search_code(query, order='desc')
    for file in results:
        if file.path.endswith('.py'):
            return file.path
    return None

def get_ast_from_code(code: str):
    try:
        return ast.parse(code)
    except SyntaxError:
        return None

def find_class_in_ast(ast_tree: ast.AST, class_name: str):
    """
    Find an AST node for the specified class within the given AST tree.
    """
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None

def fetch_class_definition(github: Github, repo: Repository, class_name: str, branch: str='main') -> tuple:
    """
    Fetch the class definition from a file located by searching the repository and parse it to find the AST node of the class.
    
    :param repo: Repository object.
    :param class_name: Class name to fetch.
    :param branch: Branch name to fetch from.
    :return: Tuple containing the AST node of the class, the class content, and the file path.
    """
    file_path = find_class_file(github=github, repo=repo, class_name=class_name, branch=branch)
    if file_path:
        contents = repo.get_contents(file_path, ref=branch)
        file_content = contents.decoded_content.decode('utf-8')
        ast_tree = get_ast_from_code(file_content)
        class_node = find_class_in_ast(ast_tree, class_name)
        if class_node:
            return (class_node, file_content, file_path)
    return (None, None, None)