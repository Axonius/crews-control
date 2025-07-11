import os
import json
from jira import JIRA, JIRAError
from crewai.tools import BaseTool
from pydantic import Field
from typing import List, Optional

def _format_comments(jira_comments_field):
    """Helper function to format JIRA comments."""
    if not jira_comments_field or not hasattr(jira_comments_field, 'comments'):
        return []
    formatted_comments = []
    for comment_obj in jira_comments_field.comments:
        author_name = "Unknown Author"
        if hasattr(comment_obj, 'author') and comment_obj.author:
            if hasattr(comment_obj.author, 'displayName'):
                author_name = comment_obj.author.displayName
            elif hasattr(comment_obj.author, 'name'):
                author_name = comment_obj.author.name
        formatted_comments.append({
            "author": author_name,
            "body": getattr(comment_obj, 'body', "No body"),
            "created": getattr(comment_obj, 'created', "No creation date")
        })
    return formatted_comments


class JiraTicketDetailsTool(BaseTool):
    """
    A tool that fetches comprehensive details from a JIRA ticket using its ID.
    This includes standard linked issues, sub-tasks, its parent issue (if any),
    and if the ticket is an Epic, its child issues.
    It can be configured to fetch specific custom fields by their name.
    """
    name: str = "JiraTicketDetailsTool"
    description: str = (
        "This tool fetches details from a JIRA ticket (including its summary, description, comments, "
        "linked issues, parent, sub-tasks, epic children, and specified custom fields) "
        "using the ticket ID and returns a JSON-formatted string."
    )

    custom_field_names_to_fetch: Optional[List[str]] = Field(default_factory=list)
    epic_issue_type_names: Optional[List[str]] = Field(default_factory=lambda: ["Epic"])
    
    # --- INTERNAL CACHE ---
    _custom_field_id_map: dict[str, str] | None = None

    class Config:
        arbitrary_types_allowed = True

    def _resolve_custom_field_ids(self, jira_client: JIRA):
        """
        Resolves custom field names to their IDs once and caches them in the instance.
        """
        if self._custom_field_id_map is not None:
            return
            
        print("First run: Resolving custom field names to IDs...")
        self._custom_field_id_map = {}
        try:
            all_fields = jira_client.fields()
            # Create a name-to-id mapping for faster lookup
            name_map = {field['name']: field['id'] for field in all_fields if field.get('custom', False)}
            
            for field_name in self.custom_field_names_to_fetch:
                if field_name in name_map:
                    self._custom_field_id_map[field_name] = name_map[field_name]
                else:
                    print(f"Warning: Custom field '{field_name}' not found in Jira instance.")

            print(f"Resolved IDs: {self._custom_field_id_map}")
        except Exception as e:
            print(f"Warning: Could not resolve custom field IDs. Custom fields will not be fetched. Error: {e}")
            self._custom_field_id_map = {}

    def _get_custom_field_values(self, issue_obj) -> dict:
        """
        Extracts values for the configured custom fields from a fetched issue object.
        """
        custom_field_data = {}
        if not self._custom_field_id_map:
            return custom_field_data

        for field_name, field_id in self._custom_field_id_map.items():
            value = None # Use None to indicate not present, vs "N/A" for present but empty
            field_value_raw = getattr(issue_obj.fields, field_id, None)
            
            if field_value_raw is not None:
                if isinstance(field_value_raw, dict):
                    if 'value' in field_value_raw:
                        value = field_value_raw['value']
                    elif 'name' in field_value_raw:
                        value = field_value_raw['name']
                    elif 'displayName' in field_value_raw:
                         value = field_value_raw['displayName']
                    else:
                        value = str(field_value_raw)
                else:
                    value = field_value_raw
            
            json_key = field_name.lower().replace(" ", "_")
            custom_field_data[json_key] = value
            
        return custom_field_data

    def _fetch_full_issue_details(self, issue_key: str, jira_client: JIRA, request_fields: list[str]) -> dict | None:
        """Fetches detailed information for a given related issue key."""
        try:
            issue = jira_client.issue(issue_key, fields=request_fields)
            
            status_name = 'N/A'
            if hasattr(issue.fields, 'status') and issue.fields.status:
                status_name = getattr(issue.fields.status, 'name', 'N/A')
            
            issuetype_name = 'N/A'
            if hasattr(issue.fields, 'issuetype') and issue.fields.issuetype:
                issuetype_name = getattr(issue.fields.issuetype, 'name', 'N/A')

            details = {
                "key": issue.key,
                "summary": getattr(issue.fields, 'summary', "Summary not available"),
                "description": getattr(issue.fields, 'description', "Description not available"),
                "status": status_name,
                "issuetype": issuetype_name,
                "comments": _format_comments(getattr(issue.fields, 'comment', None))
            }
            details.update(self._get_custom_field_values(issue))
            return details
        except JIRAError as e:
            print(f"Warning: Could not fetch full details for related issue {issue_key}: {e.text}")
            return {"key": issue_key, "summary": "Error fetching details", "description": e.text}
        except Exception as e:
            print(f"Warning: An unexpected error occurred while fetching {issue_key}: {str(e)}")
            return {"key": issue_key, "summary": "Unexpected error fetching details", "description": str(e)}

    def _run(self, ticket_id: str) -> str:
        """Use the JiraTicketDetailsTool to fetch comprehensive details for a ticket."""
        jira_server = os.getenv('JIRA_INSTANCE_URL')
        jira_username = os.getenv('JIRA_USERNAME')
        jira_password = os.getenv('JIRA_API_TOKEN')

        if not all([jira_server, jira_username, jira_password]):
            return "Error: JIRA environment variables (JIRA_INSTANCE_URL, JIRA_USERNAME, JIRA_API_TOKEN) are not set."

        try:
            jira_client = JIRA(server=jira_server, basic_auth=(jira_username, jira_password), timeout=30)
            self._resolve_custom_field_ids(jira_client)
            
            custom_field_ids = list(self._custom_field_id_map.values()) if self._custom_field_id_map else []
            base_main_fields = ["summary", "description", "status", "priority", "assignee", "created", "updated", "labels", "issuetype", "issuelinks", "subtasks", "parent", "comment", "epic"]
            base_related_fields = ["summary", "description", "comment", "status", "issuetype"]
            base_jql_fields = ["summary", "status", "issuetype", "description", "comment"]

            main_fields = list(set(base_main_fields + custom_field_ids))
            related_fields = list(set(base_related_fields + custom_field_ids))
            jql_fields = ",".join(list(set(base_jql_fields + custom_field_ids)))

            return self._fetch_jira_ticket_details_comprehensively(ticket_id, jira_client, main_fields, related_fields, jql_fields)
        except JIRAError as e:
            error_message = f"JIRA API Error: Status {e.status_code} - {e.text}"
            if e.status_code == 401: error_message += " (Unauthorized: Check credentials)"
            elif e.status_code == 404: error_message += f" (Not Found: Issue {ticket_id} may not exist)"
            return error_message
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
    
    def _fetch_jira_ticket_details_comprehensively(self, ticket_id: str, jira_client: JIRA, main_fields: list, related_fields: list, jql_fields: str) -> str:
        issue = jira_client.issue(ticket_id, fields=main_fields)

        ticket_details = {
            "key": issue.key,
            "summary": getattr(issue.fields, 'summary', "Summary not available"),
            "created": getattr(issue.fields, 'created', "N/A"),
            "updated": getattr(issue.fields, 'updated', "N/A"),
            "assignee": getattr(issue.fields.assignee, 'displayName', "Unassigned") if hasattr(issue.fields, 'assignee') and issue.fields.assignee else "Unassigned",
            "priority": getattr(issue.fields.priority, 'name', "No priority") if hasattr(issue.fields, 'priority') else "No priority",
            "status": getattr(issue.fields.status, 'name', "N/A") if hasattr(issue.fields, 'status') else "N/A",
            "issuetype": getattr(issue.fields.issuetype, 'name', "N/A") if hasattr(issue.fields, 'issuetype') else "N/A",
            "labels": getattr(issue.fields, 'labels', []),
            "description": getattr(issue.fields, 'description', "Description not available"),
        }
        ticket_details.update(self._get_custom_field_values(issue))
        ticket_details.update({
            "comments": _format_comments(getattr(issue.fields, 'comment', None)),
            "parent_issue": None,
            "related_issues": []
        })

        processed_related_keys = set()
        temp_related_issues_details = []
        
        # 1. Populate Parent Issue information
        parent_key_to_fetch = None
        parent_relationship_type = "Parent Issue"
        if hasattr(issue.fields, 'parent') and issue.fields.parent:
            parent_key_to_fetch = issue.fields.parent.key
        elif hasattr(issue.fields, 'epic') and issue.fields.epic:
            parent_key_to_fetch = issue.fields.epic.key
            parent_relationship_type = "Parent Epic"
        if parent_key_to_fetch:
            parent_details = self._fetch_full_issue_details(parent_key_to_fetch, jira_client, related_fields)
            if parent_details:
                ticket_details["parent_issue"] = {"type": parent_relationship_type, **parent_details}
                processed_related_keys.add(parent_key_to_fetch)

        # 2. Process standard issue links
        if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks:
            for link in issue.fields.issuelinks:
                link_ref = getattr(link, 'inwardIssue', getattr(link, 'outwardIssue', None))
                if link_ref and link_ref.key not in processed_related_keys:
                    detailed_issue = self._fetch_full_issue_details(link_ref.key, jira_client, related_fields)
                    if detailed_issue:
                        link_desc = link.type.inward if hasattr(link, 'inwardIssue') else link.type.outward
                        temp_related_issues_details.append({"link_type": link_desc, **detailed_issue})
                        processed_related_keys.add(link_ref.key)

        # 3. If the current issue is an Epic, fetch its children
        if issue.fields.issuetype.name in self.epic_issue_type_names:
            jql = f'"Epic Link" = {issue.key} OR parentEpic = {issue.key} ORDER BY Rank ASC'
            children_issues = jira_client.search_issues(jql, fields=jql_fields, maxResults=False)
            for child_issue in children_issues:
                if child_issue.key not in processed_related_keys:
                    child_details = self._fetch_full_issue_details(child_issue.key, jira_client, related_fields)
                    if child_details:
                        temp_related_issues_details.append({"link_type": f"Child of this Epic", **child_details})
                        processed_related_keys.add(child_issue.key)
        
        # 4. Process sub-tasks
        if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
            for subtask_ref in issue.fields.subtasks:
                if subtask_ref.key not in processed_related_keys:
                    detailed_subtask = self._fetch_full_issue_details(subtask_ref.key, jira_client, related_fields)
                    if detailed_subtask:
                        temp_related_issues_details.append({"link_type": "Sub-task", **detailed_subtask})
                        processed_related_keys.add(subtask_ref.key)
        
        ticket_details["related_issues"] = temp_related_issues_details
        return json.dumps(ticket_details, indent=4, default=str)

# Example usage (requires a .env file with Jira credentials)
if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(override=True)

    # --- 1. Example with default settings ---
    # This will use epic_issue_type_names=["Epic"] and fetch no custom fields.
    print("\n" + "="*50)
    print("DEMO: Running tool with default configuration")
    print("="*50)
    default_tool = JiraTicketDetailsTool()

    test_ticket_id = "PROJ-123"  # Replace with a valid ticket ID from your instance
    print(f"\n--- Fetching details for ticket: {test_ticket_id} ---")
    try:
        print(default_tool._run(ticket_id=test_ticket_id))
    except Exception as e:
        print(f"Failed to run tool for {test_ticket_id}. Is it a valid ticket? Error: {e}")

    # --- 2. Example with custom settings ---
    # This demonstrates how to configure the tool for a custom Jira setup.
    print("\n" + "="*50)
    print("DEMO: Running tool with custom configuration")
    print("="*50)
    
    # Instantiate the tool with custom parameters
    custom_tool = JiraTicketDetailsTool(
        custom_field_names_to_fetch=["Story Points", "Team"],  # Example custom fields
        epic_issue_type_names=["Epic", "Initiative"]      # Example epic names
    )

    test_epic_id = "PROJ-456"  # Replace with a valid Epic/Initiative ID from your instance
    print(f"\n--- Fetching details for Epic with custom settings: {test_epic_id} ---")
    try:
        # Use the custom-configured tool instance
        print(custom_tool._run(ticket_id=test_epic_id))
    except Exception as e:
        print(f"Failed to run tool for {test_epic_id}. Is it a valid epic? Error: {e}")
