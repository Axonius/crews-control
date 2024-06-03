from typing import Any, Type
from crewai_tools import BaseTool
from pydantic.v1 import BaseModel, Field
from jira import JIRA
import os

class JiraTicketSchema(BaseModel):
    """Input schema for Jira Ticket Creation Tool."""
    summary: str = Field(..., description="Summary of the Jira ticket")
    description: str = Field(..., description="Description of the Jira ticket")
    status: str = Field(..., description="Status of the Jira ticket")

class JiraTicketCreationTool(BaseTool):
    name: str = "Create Jira Ticket"
    description: str = "A tool that creates a Jira ticket."
    args_schema: Type[BaseModel] = JiraTicketSchema
    summary: str = "Default Summary"  # Default summary for the Jira ticket
    description: str = "Default Description"  # Default description for the Jira ticket
    status: str = "New"  # Default status for the Jira ticket

    def _run(self, **kwargs: Any) -> Any:
        summary = kwargs.get('summary', self.summary)
        description = kwargs.get('description', self.description)
        status = kwargs.get('status', self.status)
        jira_server = os.getenv('JIRA_INSTANCE_URL')
        jira_username = os.getenv('JIRA_USERNAME')
        jira_password = os.getenv('JIRA_API_TOKEN')
        jira_project_key = os.getenv('JIRA_CREATE_ISSUE_PROJECT_KEY')

        jira = JIRA(server=jira_server, basic_auth=(jira_username, jira_password))

        try:
            # Create the issue
            new_issue = jira.create_issue(project=jira_project_key,
                                           summary=summary,
                                           description=description,
                                           issuetype={'name': 'Task'})
            print(f"Jira ticket created successfully: {new_issue}")
            transitions = jira.transitions(new_issue)
            available_transitions = [(t['name'], t['id']) for t in transitions]
            print(f"Available transitions: {available_transitions}")
            transition_map = dict(available_transitions)
            transition_id = transition_map.get(status)

            if transition_id:
                jira.transition_issue(new_issue, transition_id)
                print(f"Issue transitioned to {status}")
            else:
                print(f"No transition found with name {status}")

            print(f"Jira ticket status updated to: {status}")
            return {'ticket_key': new_issue.key,
                    'status': status,
                    'link': f'{jira_server}/browse/{new_issue.key}'}
        except Exception as e:
            print(f"Error creating Jira ticket: {e}")
            return {'error': str(e), 'status': 'Failed'}
