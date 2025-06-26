import re
from typing import Any, Dict, List, Optional, Type
from jira import JIRA, JIRAError # type: ignore
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

class JiraReassignIssueSchema(BaseModel):
    """Input schema for Jira Reassign Issue Tool."""

    ticket_key: str = Field(
        ..., description="The key of the Jira ticket to reassign, e.g., 'PROJ-123'."
    )
    assignee_id: str = Field(
        ...,
        description="The Jira User ID (username or accountId) to assign the ticket to. "
                    "To unassign the ticket, provide the exact string 'NONE' or 'UNASSIGN'. "
                    "For default assignment (if supported by the project), provide '-1'."
    )

    @field_validator("ticket_key")
    def check_key_format(cls, v: str) -> str:
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
            raise ValueError(
                f"'{v}' does not appear to be a valid Jira key format (e.g., PROJ-123)."
            )
        return v

    @field_validator("assignee_id")
    def check_assignee_id_format(cls, v: str) -> str:
        if v.upper() in ["-1", "NONE", "UNASSIGN"]:
            return v
        if not v or v.isspace():
            raise ValueError(
                "Assignee ID, if not a special keyword ('NONE', 'UNASSIGN', '-1'), must be a non-empty string."
            )
        return v

class JiraReassignIssueTool(BaseTool):
    name: str = "jira_reassign_issue"
    description: str = (
        "Reassigns a specified Jira ticket to a given user (identified by username or accountId). "
        "Can also be used to assign to default or unassign based on the provided assignee_id string."
    )
    args_schema: Type[JiraReassignIssueSchema] = JiraReassignIssueSchema
    
    allowed_project_prefixes: Optional[List[str]] = Field(
        default=None,
        description="Optional list of allowed project key prefixes to work on (e.g., ['PROJA-', 'PROJB-']). If provided, the tool will only operate on tickets with these prefixes.",
    )

    # This is a Pydantic field and it's required because it has no default
    # and is not Optional. It must be present in the kwargs passed to __init__.
    jira_client: JIRA

    def __init__(self, **kwargs: Any):
        """
        Initializes the tool. All arguments, including 'jira_client' and
        'allowed_project_prefixes', are expected to be passed as keyword arguments.
        """
        super().__init__(**kwargs)
        if getattr(self, 'jira_client', None) is None:
             raise ValueError("JiraReassignIssueTool requires an initialized JIRA client to be passed via keyword arguments.")

    def _run(self, **kwargs: Any) -> Dict[str, str]:
        ticket_key = str(kwargs.get("ticket_key"))
        assignee_id_input = str(kwargs.get("assignee_id"))

        if self.allowed_project_prefixes:
            if not any(
                ticket_key.startswith(prefix) for prefix in self.allowed_project_prefixes
            ):
                error_msg = f"Operation on ticket '{ticket_key}' is not allowed. This tool is restricted to projects with the following prefixes: {self.allowed_project_prefixes}."
                print(f"Validation Error: {error_msg}")
                return {"error": error_msg, "status": "Failed Validation - Project"}

        assignee_for_api: Optional[str]
        if assignee_id_input.upper() in ["NONE", "UNASSIGN"]:
            assignee_for_api = None
        elif assignee_id_input == "-1":
            assignee_for_api = "-1"
        else:
            assignee_for_api = assignee_id_input

        try:
            print(f"Verifying ticket '{ticket_key}' exists...")
            issue: Any
            try:
                issue = self.jira_client.issue(
                    ticket_key, fields="assignee,id"
                )
                print(
                    f"Ticket {ticket_key} found. Current assignee: {getattr(issue.fields.assignee, 'displayName', 'Unassigned')}"
                )
            except JIRAError as e:
                if e.status_code == 404:
                    error_msg = f"Target ticket '{ticket_key}' not found."
                else:
                    error_msg = f"Error verifying target ticket '{ticket_key}'. API Error: {e.status_code} - {e.text}"
                print(f"Error: {error_msg}")
                return {"error": error_msg, "status": "Failed Validation - Ticket"}

            print(
                f"Attempting to reassign ticket {ticket_key} to '{assignee_for_api if assignee_for_api is not None else 'Unassigned'}' (API value)..."
            )

            update_payload = {"assignee": None}
            if assignee_for_api is not None:
                 update_payload = {"assignee": {"accountId": assignee_for_api}}
            
            try:
                issue.update(fields=update_payload)
                print(
                    f"Jira API call for reassignment of {ticket_key} to '{assignee_for_api if assignee_for_api is not None else 'Unassigned'}' was executed."
                )
            except JIRAError as e: 
                print(f"JIRAError during issue.update() for ticket {ticket_key}: {e.status_code} - {e.text}")
                raise e 
            except Exception as e:
                print(f"An unexpected error occurred during issue update for ticket {ticket_key}: {e}")
                raise e 
            
            action_desc = ""
            assigned_to_message = assignee_id_input
            if assignee_for_api is None:
                action_desc = "unassigned"
                assigned_to_message = "Unassigned"
            elif assignee_for_api == "-1":
                action_desc = "assigned to default"
            else:
                action_desc = f"reassigned to '{assignee_id_input}'"

            success_msg = f"Successfully {action_desc} ticket {ticket_key}."
            print(success_msg)
            return {
                "message": success_msg,
                "status": "Success",
                "ticket_key": ticket_key,
                "assigned_to": assigned_to_message,
            }

        except JIRAError as e:
            error_msg_detail = f"Jira API error processing reassignment for ticket '{ticket_key}' with input '{assignee_id_input}'. Error: {e.status_code} - {e.text}"
            if e.status_code == 400:
                if "user" in e.text.lower() or "assignee" in e.text.lower():
                    error_msg_detail = f"Cannot assign ticket '{ticket_key}' to '{assignee_id_input}'. User may not exist, be inactive, or not be assignable for this project. Details: {e.text}"
                else:
                    error_msg_detail = f"Failed to reassign ticket '{ticket_key}'. Bad Request (check workflow, permissions, or assignee ID format). Details: {e.text}"
            elif e.status_code == 401:
                error_msg_detail = f"Unauthorized to reassign ticket '{ticket_key}'. Check Jira credentials. Details: {e.text}"
            elif e.status_code == 403:
                error_msg_detail = f"Permission denied: Cannot reassign ticket '{ticket_key}'. Check user permissions for the project/issue. Details: {e.text}"
            elif e.status_code == 404:
                if "user" in e.text.lower() or "assignee" in e.text.lower():
                    error_msg_detail = f"Assignee user '{assignee_id_input}' not found for ticket '{ticket_key}'. Details: {e.text}"
                else: 
                    error_msg_detail = f"Ticket '{ticket_key}' not found during reassignment process. Details: {e.text}"
            print(f"Error: {error_msg_detail}")
            return {"error": error_msg_detail, "status": "Failed Execution - API"}
        except Exception as e:
            error_msg = f"An unexpected error occurred while reassigning ticket {ticket_key}: {e}"
            print(f"Error: {error_msg}")
            return {"error": error_msg, "status": "Failed Unexpected"}
