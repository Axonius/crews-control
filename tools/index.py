import typing
from typing import Callable
import os

from crewai_tools.tools.directory_search_tool.directory_search_tool import DirectorySearchTool
from crewai_tools.tools.serper_dev_tool.serper_dev_tool import SerperDevTool
from crewai_tools import SeleniumScrapingTool

from langchain_community.agent_toolkits.jira.toolkit import JiraToolkit
from langchain_community.utilities.jira import JiraAPIWrapper
from tools.custom.github_search import GitHubSearchTool
from tools.custom.find_method_implementation import FindMethodImplementationTool
from tools.custom.pr_details import GitHubPRDetailsTool
from tools.custom.create_jira_issue import JiraTicketCreationTool
from tools.custom.website_search_tool import WebsiteContentQueryTool
from tools.custom.human import HumanTool
from tools.custom.website_search_tool import WebsiteContentQueryTool
from tools.custom.youtube import YoutubeChannelSearchTool
from embedchain import App

from langchain.agents import load_tools
from utils import get_embedchain_settings
from utils import validate_env_vars, EnvironmentVariableNotSetError
import rich
from rich.padding import Padding

required_vars = [
    "JIRA_API_TOKEN",
    "JIRA_USERNAME",
    "JIRA_INSTANCE_URL",
    "JIRA_CREATE_ISSUE_PROJECT_KEY",
    "GITHUB_TOKEN",
    "SERPER_API_KEY"
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

jira = JiraAPIWrapper(
    jira_api_token=os.getenv('JIRA_API_TOKEN'),
    jira_username=os.getenv('JIRA_USERNAME'),
    jira_instance_url=os.getenv('JIRA_INSTANCE_URL')
)
jira_toolkit = JiraToolkit.from_jira_api_wrapper(jira)

_TOOLS_MAP: dict[str, Callable] = {
    'serper': lambda _: SerperDevTool(),
    'website_search': lambda app: WebsiteContentQueryTool(app=app),
    'youtube': lambda app: YoutubeChannelSearchTool(app=app),
    'human': lambda _: HumanTool(),
    'read_file': lambda _: load_tools(['read_file'])[0],
    'directory_search': lambda app: DirectorySearchTool(app=app),
    'jql_query': lambda _: jira_toolkit.get_tools()[0], # 'JQL Query
    'selenium': lambda _: SeleniumScrapingTool(),
    'github_search': lambda _: GitHubSearchTool(),
    'fetch_pr_content': lambda _: GitHubPRDetailsTool(),
    'FindMethodImplementationTool': lambda _: FindMethodImplementationTool(),
    'create_issue': lambda _: JiraTicketCreationTool(),
}

def get_tool(tool_name: str, task_id: typing.Optional[str] = None) -> Callable:
    app = App.from_config(config=get_embedchain_settings(task_id=task_id or 'shared'))
    return _TOOLS_MAP[tool_name](app)

def list_tools():
    return _TOOLS_MAP.keys()