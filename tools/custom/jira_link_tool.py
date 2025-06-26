import os
import re
from typing import Any, Dict, List, Optional, Tuple, Type # Added Type for args_schema

from jira import JIRA, JIRAError
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

class JiraLinkTicketsSchema(BaseModel):
    """Input schema for Jira Link Tickets Tool."""
    source_ticket_key: str = Field(..., description="The key of the source Jira ticket where the link originates (outward issue), e.g., 'PROJA-123'.")
    target_ticket_key: str = Field(..., description="The key of the target Jira ticket being linked to (inward issue), e.g., 'PROJB-456'.")
    link_type_name: str = Field(..., description="The name of the Jira issue link type, e.g., 'Relates', 'Blocks', 'Duplicates'. This must exactly match a configured link type in your Jira instance.")

    @field_validator('source_ticket_key', 'target_ticket_key')
    def check_key_format(cls, v: str) -> str:
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
            raise ValueError(f"'{v}' does not appear to be a valid Jira key format (e.g., PROJ-123).")
        return v

class JiraLinkTicketsTool(BaseTool):
    name: str = "link_jira_tickets"
    description: str = ("A tool that links two Jira tickets using a specified relationship type (e.g., 'Relates', 'Blocks'). "
                        "Provide the source ticket, the target ticket, and the exact link type name.")
    args_schema: Type[JiraLinkTicketsSchema] = JiraLinkTicketsSchema # Use Type here
    
    allowed_link_pairs: Optional[List[Tuple[str, str]]] = Field(
        default=None,
        description="Optional list of allowed project link pairings, e.g., [('PROJA-', 'PROJB-')]. If provided, links are only allowed between these project pairs."
    )
    
    # This is a Pydantic field and it's required because it has no default
    # and is not Optional. It must be present in the kwargs passed to __init__.
    jira_client: JIRA 

    def __init__(self, **kwargs: Any):
        """
        Initializes the tool. All arguments, including 'jira_client' and
        'allowed_link_pairs', are expected to be passed as keyword arguments.
        """
        super().__init__(**kwargs) # Pydantic initializes ALL its fields from kwargs.
                                    # It will raise an error if 'jira_client' is missing in kwargs.
        
        # After Pydantic initialization, self.jira_client should be set.
        # This check is somewhat redundant if Pydantic already enforced 'jira_client' presence,
        # but it's a good safeguard for clarity or if 'None' somehow passed Pydantic validation
        # (which it shouldn't for a non-Optional field without a default).
        if getattr(self, 'jira_client', None) is None:
             raise ValueError("JiraLinkTicketsTool requires an initialized JIRA client to be passed via keyword arguments.")

    def _run(self, **kwargs: Any) -> Dict[str, str]:
        source_ticket_key = str(kwargs.get('source_ticket_key'))
        target_ticket_key = str(kwargs.get('target_ticket_key'))
        link_type_name = str(kwargs.get('link_type_name'))

        if source_ticket_key == target_ticket_key:
            print(f"Validation Error: Source ({source_ticket_key}) and target ({target_ticket_key}) ticket keys cannot be the same.")
            return {'error': "Source and target ticket keys cannot be the same.", 'status': 'Failed Validation'}

        if self.allowed_link_pairs:
            source_prefix = source_ticket_key.split('-')[0] + '-'
            target_prefix = target_ticket_key.split('-')[0] + '-'
            
            is_valid_pair = False
            # Normalize allowed prefixes to ensure they end with a hyphen and compare case-insensitively
            normalized_allowed_pairs = [
                (p1.upper() if p1.endswith('-') else p1.upper() + '-', 
                 p2.upper() if p2.endswith('-') else p2.upper() + '-')
                for p1, p2 in self.allowed_link_pairs
            ]
            current_pair_normalized = (source_prefix.upper(), target_prefix.upper())

            for pair1_norm, pair2_norm in normalized_allowed_pairs:
                if (current_pair_normalized[0] == pair1_norm and current_pair_normalized[1] == pair2_norm) or \
                   (current_pair_normalized[0] == pair2_norm and current_pair_normalized[1] == pair1_norm):
                    is_valid_pair = True
                    break
            
            if not is_valid_pair:
                error_msg = f"Linking from project '{source_prefix[:-1]}' to '{target_prefix[:-1]}' is not an allowed operation. Permitted pairings (case-insensitive for prefixes) are: {self.allowed_link_pairs}"
                print(f"Validation Error: {error_msg}")
                return {'error': error_msg, 'status': 'Failed Validation - Project Link'}

        try:
            print(f"Verifying existence of tickets: '{source_ticket_key}' and '{target_ticket_key}'.")
            try:
                self.jira_client.issue(source_ticket_key, fields='id')
                self.jira_client.issue(target_ticket_key, fields='id')
                print("Both tickets verified successfully.")
            except JIRAError as e:
                error_msg = ""
                if e.status_code == 404:
                    error_msg = f"Could not find one or both tickets. Ensure both '{source_ticket_key}' and '{target_ticket_key}' exist. Details: {e.text}"
                else:
                    error_msg = f"API error verifying tickets for linking. Check keys and permissions. Error: {e.status_code} - {e.text}"
                print(f"Error: {error_msg}")
                return {'error': error_msg, 'status': 'Failed Validation - Ticket'}

            links = self.jira_client.issue(source_ticket_key, fields='issuelinks').fields.issuelinks
            link_type_name_lower = link_type_name.lower() # For case-insensitive comparison
            for link in links:
                # Check for outward link (source -> target)
                if (hasattr(link, 'outwardIssue') and
                    link.outwardIssue.key == target_ticket_key and
                    link.type.name.lower() == link_type_name_lower):
                    info_msg = f"Link '{link_type_name}' from {source_ticket_key} to {target_ticket_key} already exists."
                    print(info_msg)
                    return {'message': info_msg, 'status': 'Success (Already Exists)'}
                # Check for inward link if the type implies directionality and we want to avoid duplicate reverse links
                # This part depends on how Jira handles link types (e.g. "blocks" vs "is blocked by")
                # For simplicity, only checking outward link existence here.

            print(f"Attempting to create link: {source_ticket_key} --({link_type_name})--> {target_ticket_key}")
            self.jira_client.create_issue_link(
                type=link_type_name,
                inwardIssue=target_ticket_key, # The issue being pointed TO
                outwardIssue=source_ticket_key, # The issue where the link STARTS
            )
            success_msg = f"Successfully linked {source_ticket_key} to {target_ticket_key} as '{link_type_name}'."
            print(success_msg)
            return {'message': success_msg, 'status': 'Success'}

        except JIRAError as e:
            error_msg_detail = f"Jira API error creating link between {source_ticket_key} and {target_ticket_key}. Error: {e.status_code} - {e.text}"
            if e.status_code == 400 and "No issue link type" in e.text.lower():
                error_msg_detail = f"The link type name '{link_type_name}' does not exist or is not applicable in this Jira instance."
            elif "already exists" in e.text.lower(): 
                 error_msg_detail = f"Link ({link_type_name}) from {source_ticket_key} to {target_ticket_key} already exists (reported by API)."
                 return {'message': error_msg_detail, 'status': 'Success (Already Exists)'}
            print(f"Error: {error_msg_detail}")
            return {'error': error_msg_detail, 'status': 'Failed Execution - API'}
        except Exception as e:
            error_msg = f"An unexpected error occurred during the link process between {source_ticket_key} and {target_ticket_key}: {e}"
            print(f"Error: {error_msg}")
            return {'error': error_msg, 'status': 'Failed Unexpected'}
