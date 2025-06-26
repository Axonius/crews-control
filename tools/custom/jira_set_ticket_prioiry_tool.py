import re
from typing import Any, Dict, List, Optional, Type, Union
from jira import JIRA, JIRAError
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

class JiraSetPrioritySchema(BaseModel):
    """Input schema for JiraTicketSetPriority tool."""
    ticket_id: str = Field(..., description="The JIRA ticket ID or key (e.g., 'PROJ-123').")
    priority_value: str = Field(..., description="The exact string value for the priority to be set. This typically corresponds to an option in the 'VulnSeverity' (customfield_1234) field (e.g., 'High', 'Critical').")

    @field_validator('ticket_id')
    def validate_ticket_id(cls, v: str) -> str:
        if not v or v.isspace():
            raise ValueError("Ticket ID cannot be empty.")
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
            raise ValueError(f"Error: Ticket ID '{v}' does not strictly match 'PROJ-123' format!")
        return v

    @field_validator('priority_value')
    def validate_priority_value(cls, v: str) -> str:
        if not v or v.isspace():
            raise ValueError("Priority value cannot be empty.")
        return v

class JiraTicketSetPriority(BaseTool):
    name: str = "set_jira_ticket_vulnerability_severity"
    description: str = (
        "Sets the 'VulnSeverity' (customfield_1234) of a JIRA ticket. "
        "Requires the ticket ID (e.g., 'PROJ-123') and the exact priority string value "
        "(e.g., 'High', 'Medium') that is valid for the 'VulnSeverity' field. "
        "Operation can be restricted by allowed project prefixes."
    )
    args_schema: Type[JiraSetPrioritySchema] = JiraSetPrioritySchema

    jira_client: JIRA # Pydantic field, required

    allowed_project_prefixes: Optional[List[str]] = Field(
        default=None,
        description="Optional list of allowed project key prefixes (e.g., ['PROJ-', 'TEST-']). If provided, the tool will only operate on tickets with these prefixes."
    )

    def __init__(self, **kwargs: Any):
        """
        Initializes the tool. All arguments, including 'jira_client' and
        'allowed_project_prefixes', are expected to be passed as keyword arguments.
        """
        super().__init__(**kwargs)
        
        if getattr(self, 'jira_client', None) is None:
             raise ValueError("JiraTicketSetPriority tool requires an initialized JIRA client to be passed via keyword arguments.")

    def _run(self, **kwargs: Any) -> Union[str, Dict[str, str]]:
        ticket_id = str(kwargs.get('ticket_id'))
        priority_value = str(kwargs.get('priority_value'))

        VULN_SEVERITY_CUSTOM_FIELD_ID = "customfield_1234" # set this to the custom filed of the vuln severity

        if self.allowed_project_prefixes:
            project_key_part = ticket_id.split('-', 1)[0]
            project_prefix_to_check = project_key_part + '-'
            
            normalized_allowed_prefixes = [
                prefix if prefix.endswith('-') else prefix + '-' 
                for prefix in self.allowed_project_prefixes
            ]

            if not any(
                project_prefix_to_check.upper() == prefix.upper() for prefix in normalized_allowed_prefixes
            ):
                error_msg = (f"Operation on ticket '{ticket_id}' is not allowed. "
                             f"Its project prefix '{project_prefix_to_check[:-1]}' is not in the allowed list: " # Display without trailing hyphen
                             f"{[p[:-1] if p.endswith('-') else p for p in normalized_allowed_prefixes]}.")
                print(f"Validation Error: {error_msg}")
                return {"error": error_msg, "status": "Failed Validation - Project"}

        print(f"Attempting to set '{VULN_SEVERITY_CUSTOM_FIELD_ID}' for ticket '{ticket_id}' to '{priority_value}'.")

        try:
            print(f"Fetching ticket '{ticket_id}' to verify existence...")
            issue = self.jira_client.issue(ticket_id)
            print(f"Ticket '{ticket_id}' found: {issue.fields.summary}")
            try:
                field_meta = self.jira_client.editmeta(issue.key)
                if VULN_SEVERITY_CUSTOM_FIELD_ID in field_meta['fields']:
                    customfield_options = field_meta['fields'][VULN_SEVERITY_CUSTOM_FIELD_ID].get('allowedValues', [])
                    print(f"Available options for '{VULN_SEVERITY_CUSTOM_FIELD_ID}' (VulnSeverity) on ticket {issue.key}:")
                    for option in customfield_options:
                        print(f"  - Value: '{option['value']}' (ID: {option['id']})")
                else:
                    print(f"Warning: Custom field '{VULN_SEVERITY_CUSTOM_FIELD_ID}' not found in editmeta for ticket {issue.key}. Attempting to set priority directly.")
            except JIRAError as e_meta:
                print(f"Warning: Could not fetch edit metadata for ticket {issue.key} to list priority options: {e_meta.status_code} - {e_meta.text}")
            except Exception as e_meta_other:
                print(f"Warning: An unexpected error occurred while fetching edit metadata: {e_meta_other}")

            print(f"Updating ticket '{ticket_id}' with '{VULN_SEVERITY_CUSTOM_FIELD_ID}' = '{priority_value}'...")
            issue.update(fields={VULN_SEVERITY_CUSTOM_FIELD_ID: {"value": priority_value}})
            
            success_message = f"Successfully set '{VULN_SEVERITY_CUSTOM_FIELD_ID}' for ticket {ticket_id} ({issue.key}) to '{priority_value}'. Ticket URL: {issue.permalink()}"
            print(success_message)
            return {"status": "Success", "message": success_message, "ticket_url": issue.permalink()}

        except JIRAError as e:
            error_detail = f"JIRA API error while setting priority for ticket '{ticket_id}': {e.status_code} - {e.text}"
            if e.status_code == 400:
                error_detail = (f"Failed to set priority for ticket '{ticket_id}' to '{priority_value}'. "
                                f"This value might be invalid for the '{VULN_SEVERITY_CUSTOM_FIELD_ID}' field. "
                                f"Original error: {e.status_code} - {e.text}")
            elif e.status_code == 404:
                 error_detail = f"Ticket '{ticket_id}' not found while attempting to set priority."

            print(f"Error: {error_detail}")
            return {"status": "Error", "error": error_detail}
        except Exception as e:
            error_detail = f"An unexpected error occurred while setting priority for ticket '{ticket_id}': {e}"
            print(f"Error: {error_detail}")
            return {"status": "Error", "error": error_detail}
