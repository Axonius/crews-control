from typing import Any, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from jira import JIRA
import os
import re

class JiraTicketSchema(BaseModel):
    """Input schema for Jira Ticket Creation Tool."""
    summary: str = Field(..., description="Summary of the Jira ticket")
    description: str = Field(..., description="Description of the Jira ticket")
    status: str = Field(..., description="Status of the Jira ticket")
    issue_type: Optional[str] = Field(None, description="Optional issue type for the Jira ticket. If not provided, the default from the environment variable will be used.")

class JiraTicketCreationTool(BaseTool):
    name: str = "Create Jira Ticket"
    description: str = "A tool that creates a Jira ticket."
    args_schema: type[JiraTicketSchema] = JiraTicketSchema

    def _run(self, **kwargs: Any) -> Any:
        summary = kwargs.get('summary')
        description = kwargs.get('description')
        status = kwargs.get('status')
        issue_type = kwargs.get('issue_type')
        jira_server = os.getenv('JIRA_INSTANCE_URL')
        jira_username = os.getenv('JIRA_USERNAME')
        jira_password = os.getenv('JIRA_API_TOKEN')
        jira_project_key = os.getenv('JIRA_CREATE_ISSUE_PROJECT_KEY')
        default_issue_type = os.getenv('JIRA_CREATE_ISSUE_TYPE')

        jira = JIRA(server=jira_server, basic_auth=(jira_username, jira_password))

        try:
            pr_number = None
            jira_ticket_number = None

            # Extract PR number
            if "PR #" in summary:
                pr_number = summary.split('#')[-1].split(' ')[0]
                if not pr_number.isdigit():
                    pr_number = None

            if pr_number:
                jql_query = f'project = "{jira_project_key}" AND summary ~ "PR #{pr_number}"'
            else:
                match = re.search(r"([A-Z]+-\d+)", summary)
                if match:
                    jira_ticket_number = match.group(1)
                    jql_query = f'project = "{jira_project_key}" AND summary ~ "{jira_ticket_number}"'
                else:
                    raise ValueError("Summary must contain either a PR number or a Jira ticket number.")

            existing_issues = jira.search_issues(jql_query)

            if existing_issues:
                existing_issue = existing_issues[0]
                jira.add_comment(existing_issue, description)
                print(f"Jira ticket updated successfully: {existing_issue}")
                issue = existing_issue
            else:
                issue_type_to_use = issue_type if issue_type else default_issue_type
                new_issue = jira.create_issue(project=jira_project_key,
                                            summary=summary,
                                            description=description,
                                            issuetype={'name': issue_type_to_use})
                print(f"Jira ticket created successfully: {new_issue}")
                issue = new_issue

            transitions = jira.transitions(issue)
            available_transitions = [(t['name'], t['id']) for t in transitions]
            print(f"Available transitions: {available_transitions}")
            transition_map = dict(available_transitions)
            transition_id = transition_map.get(status)

            if transition_id:
                jira.transition_issue(issue, transition_id)
                print(f"Issue transitioned to {status}")
            else:
                print(f"No transition found with name {status}")

            print(f"Jira ticket status updated to: {status}")
            return {'ticket_key': issue.key,
                    'status': status,
                    'link': f'{jira_server}/browse/{issue.key}'}

        except ValueError as ve:
            print(f"Error creating Jira ticket: {ve}")
            return {'error': str(ve), 'status': 'Failed'}
        except Exception as e:
            print(f"Error creating Jira ticket: {e}")
            return {'error': str(e), 'status': 'Failed'}
