import typing
from typing import Callable, List, Dict, Any, Optional, Type
import os

from langchain_community.agent_toolkits.jira.toolkit import JiraToolkit
from langchain_community.utilities.jira import JiraAPIWrapper
from tools.custom.github_search import GitHubSearchTool
from tools.custom.find_method_implementation import FindMethodImplementationTool
from tools.custom.pr_details import GitHubPRDetailsTool, GitHubPRDiffTool
from tools.custom.create_jira_issue import JiraTicketCreationTool
from tools.custom.jira_link_tool import JiraLinkTicketsTool
from tools.custom.jira_attach_tool import JiraAttachFileTool
from tools.custom.jira_fetch_ticket_details_tool import JiraTicketDetailsTool
from tools.custom.jira_set_ticket_prioiry_tool import JiraTicketSetPriority
from tools.custom.jira_reassign_ticket_tool import JiraReassignIssueTool
from tools.custom.human import HumanTool
from tools.custom.git_search_tool import GitSearchTool
from tools.custom.fetch_file_content_tool import GitFileContentQueryTool
from tools.custom.github_fetch_file_paginated import GitHubFilePaginator
from tools.custom.confluence_fetch import ConfluenceDataQueryTool
from tools.custom.image_analyzer_tool import AdvancedImageAnalyzerTool, AzureConfig, JiraConfig, ConfluenceConfig

from langchain_community.agent_toolkits.load_tools import load_tools
from utils import validate_env_vars, EnvironmentVariableNotSetError
from utils import get_embedchain_settings
import rich
from rich.padding import Padding
from crewai.tools import BaseTool
from jira import JIRA, JIRAError
from langchain_community.tools.jira.tool import JiraAction
from pydantic import BaseModel, Field
class JqlQueryToolSchema(BaseModel):
    jql_query: str = Field(..., description="The valid JQL (Jira Query Language) string to execute for searching issues.")

class CrewAIJiraTool(BaseTool):
    """
    Wrapper to make JiraAction (specifically for JQL mode) compatible with CrewAI.
    Executes a JQL query.
    """
    name: str = "jql_query"
    description: str = """Executes a JQL (Jira Query Language) search query against Jira and returns the results.
Input MUST be a single string containing only the valid JQL query.
Example valid JQL queries:
'project = "PROJ" AND status = Open ORDER BY created DESC'
'assignee = currentUser() AND resolution = Unresolved'"""
    args_schema: Type[BaseModel] = JqlQueryToolSchema
    jira_action: JiraAction # Store the underlying Langchain JiraAction

    def __init__(self, jira_action: JiraAction, **kwargs):
        """Initialize with a JiraAction instance (must be JQL mode)."""
        if not (hasattr(jira_action, 'mode') and jira_action.mode == 'jql'):
            raise ValueError("The provided JiraAction must be configured with mode='jql'")

        super().__init__(jira_action=jira_action, **kwargs)

        # Preserve API wrapper to ensure authentication stays intact
        if hasattr(jira_action, "api_wrapper"):
            object.__setattr__(self, "api_wrapper", jira_action.api_wrapper)

    def _run(self, jql_query: str):
        """Implements CrewAI's expected method and delegates execution to JiraAction.run."""
        if not isinstance(jql_query, str) or not jql_query.strip():
             return "Error: Input must be a non-empty JQL query string."

        try:
            result = self.jira_action.run(tool_input=jql_query)
            return str(result) # Ensure string output
        except Exception as e:
            error_str = str(e)
            if "Error in the JQL Query" in error_str or "JQL" in error_str:
                 return f"Error: Invalid JQL Syntax. Jira reported: {error_str}"
            return f"Error during JQL search using tool '{self.name}': {type(e).__name__} - {error_str}"

    class Config:
        arbitrary_types_allowed = True  # Allow non-Pydantic types like JiraAction

# For custom jira tools using python-jira
def get_jira_instance(jira_api_token: str,
                      jira_username: str,
                      jira_instance_url: str):
    try:
        jira = JIRA(server=jira_instance_url, basic_auth=(jira_username, jira_api_token))
        # Test connection by getting server info
        _ = jira.server_info()
        return jira
    except JIRAError as e:
        raise ConnectionAbortedError(
            f"Jira API connection/authentication error: {e.status_code} - {e.text}"
        )
    except Exception as e:
        raise ConnectionAbortedError(
            f"An unexpected error occurred during Jira connection: {e}"
        )
python_jira = get_jira_instance(
    jira_api_token = os.environ["JIRA_API_TOKEN"],
    jira_username = os.environ["JIRA_USERNAME"],
    jira_instance_url = os.environ["JIRA_INSTANCE_URL"]
)
# for langchain JiraToolkit using atlassian-python-api
jira = JiraAPIWrapper(
    jira_api_token=os.getenv('JIRA_API_TOKEN'),
    jira_username=os.getenv('JIRA_USERNAME'),
    jira_instance_url=os.getenv('JIRA_INSTANCE_URL'),
    jira_cloud="true"
)
jira_toolkit = JiraToolkit.from_jira_api_wrapper(jira)
jql_tool = jira_toolkit.get_tools()[0]
crewai_jira_tool = CrewAIJiraTool(jql_tool)

def get_jira_link_pairs() -> list[tuple[str, str]]:
    """
    Parses the JIRA_LINK_ALLOWED_PAIRS environment variable.
    Format: "PREFIX1,PREFIX2|PREFIX3,PREFIX4"
    """
    pairs_env_var = os.getenv('JIRA_LINK_ALLOWED_PAIRS')
    if not pairs_env_var:
        return []

    allowed_pairs = []
    for pair_str in pairs_env_var.split('|'):
        parts = [p.strip() for p in pair_str.split(',')]
        if len(parts) == 2:
            allowed_pairs.append(tuple(parts))
    return allowed_pairs

_TOOLS_MAP: dict[str, Callable] = {
    'human': lambda: HumanTool(),
    'read_file': lambda: load_tools(['read_file'])[0],
    'jql_query': lambda **kwargs: crewai_jira_tool(**kwargs),
    'github_search': lambda **kwargs: GitHubSearchTool(**kwargs),
    'fetch_pr_details': lambda **kwargs: GitHubPRDetailsTool(**kwargs),
    'fetch_pr_diff': lambda **kwargs: GitHubPRDiffTool(**kwargs),
    'FindMethodImplementationTool': lambda **kwargs: FindMethodImplementationTool(**kwargs),
    'create_issue': lambda **kwargs: JiraTicketCreationTool(**kwargs),
    'link_issue': lambda **kwargs: JiraLinkTicketsTool(
        jira_client=python_jira,
        allowed_link_pairs=get_jira_link_pairs(),
        **kwargs
    ),
    'issue_attach_file': lambda **kwargs: JiraAttachFileTool(
        jira_client=python_jira,
        allowed_project_prefixes=prefixes.split(',') if (
            prefixes := os.getenv('JIRA_ATTACH_ALLOWED_PREFIXES')
        ) else None,
        **kwargs
    ),
    'jira_reassign_issue': lambda **kwargs: JiraReassignIssueTool(
        jira_client=python_jira,
        allowed_project_prefixes=prefixes.split(',') if (
            prefixes := os.getenv('JIRA_REASSIGN_ALLOWED_PREFIXES')
        ) else None,
        **kwargs
    ),
    'jira_set_ticket_priority': lambda **kwargs: JiraTicketSetPriority(
        jira_client=python_jira,
        allowed_project_prefixes=prefixes.split(',') if (
            prefixes := os.getenv('JIRA_SETPRIORITY_ALLOWED_PREFIXES')
        ) else None,
        **kwargs
    ),
    'git_search': lambda **kwargs: GitSearchTool(**kwargs),
    'fetch_file_content': lambda **kwargs: GitFileContentQueryTool(**kwargs),
    'paginate_github_file': lambda **kwargs: GitHubFilePaginator(**kwargs),
    'jira_get_issue_details': lambda **kwargs: JiraTicketDetailsTool(**kwargs),
    'confluence': lambda **kwargs: ConfluenceDataQueryTool(**kwargs),
    'FinalAnswerTool': lambda **kwargs: FinalAnswerTool(**kwargs),
    'image_analyzer_tool': lambda **kwargs: AdvancedImageAnalyzerTool(
         AzureConfig(
            api_key=os.environ["AZURE_API_KEY"],
            endpoint=os.environ["AZURE_API_BASE"],
            api_version=os.environ["AZURE_API_VERSION"],
            vision_deployment=os.environ["AZURE_OPENAI_VISION_DEPLOYMENT"]
        ),
        JiraConfig(
            instance_url=os.environ['JIRA_INSTANCE_URL'],
            username=os.environ['JIRA_USERNAME'],
            api_token=os.environ['JIRA_API_TOKEN']
        ),
        ConfluenceConfig(
            endpoint_url=os.environ['CONFLUENCE_ENDPOINT'],
            username=os.environ['CONFLUENCE_API_USER'],
            api_token=os.environ['CONFLUENCE_API_TOKEN']
        ),
        **kwargs
    ),
}

class FinalAnswerTool(BaseTool):
     name: str = "FinalAnswerTool"
     description: str = "Tool to generate the final answer"
     def _run(self, final_answer: str) -> str:
          return final_answer
 
required_vars = [
    "JIRA_API_TOKEN",
    "JIRA_USERNAME",
    "JIRA_INSTANCE_URL",
    "JIRA_CREATE_ISSUE_PROJECT_KEY",
    "JIRA_CREATE_ISSUE_TYPE",
    "JIRA_LINK_ALLOWED_PAIRS",
    "JIRA_ATTACH_ALLOWED_PREFIXES",
    "JIRA_SETPRIORITY_ALLOWED_PREFIXES",
    "JIRA_REASSIGN_ALLOWED_PREFIXES",
    "GITHUB_TOKEN",
    "SERPER_API_KEY",
    "LLM_NAME",
    "EMBEDDER_NAME",
    "CONFLUENCE_ENDPOINT",
    "CONFLUENCE_API_USER",
    "CONFLUENCE_API_TOKEN",
]

try:
    validate_env_vars(*required_vars)
except EnvironmentVariableNotSetError as e:
        rich.print(
            Padding(
                f"[bold red]Error: {str(e)}[/bold red]",
                (2, 4),
                expand=True,
                style="bold red",
            )
        )
        os._exit(1)

def get_tool(tool_name: str, task_id: typing.Optional[str] = None, **kwargs) -> Callable:
    try:
        return _TOOLS_MAP[tool_name](**kwargs)
    except KeyError as e:
        raise ValueError(f"Tool '{tool_name}' not found: {e}")
    except Exception as e:
        raise Exception(f"Failed to get tool: {e}")
