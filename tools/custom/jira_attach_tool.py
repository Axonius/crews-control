import io
import re
import os
import json
import argparse
from typing import Any, Dict, List, Optional, Type

from jira import JIRA, JIRAError
from pydantic import BaseModel, Field, field_validator, model_validator
from dotenv import load_dotenv

from crewai.tools import BaseTool


# --- Pydantic Schemas for Tool Arguments ---

class AttachmentItem(BaseModel):
    """Schema for a single item in the batch attachment list."""
    filename: str = Field(..., description="The desired filename for the attachment in Jira (e.g., 'results.md', 'scan_output.json').")
    file_content: str = Field(..., description="The content of the file provided as a single string.")

    @field_validator('filename')
    def check_filename(cls, v: str) -> str:
        if not v or '/' in v or '\\' in v:
             raise ValueError(f"Invalid filename: '{v}'. Cannot be empty or contain path separators.")
        return v

class JiraAttachFileSchema(BaseModel):
    """Input schema for Jira Attach File Tool. Supports both single and batch modes."""
    ticket_key: str = Field(..., description="The key of the target Jira ticket, e.g., 'PROJ-123'.")
    
    # Batch mode: a list of attachment items
    attachments: Optional[List[AttachmentItem]] = Field(
        default=None, 
        description="For batch mode, provide a list of files to attach. Each item must have 'filename' and 'file_content'."
    )
    
    # Single file mode (for backward compatibility)
    filename: Optional[str] = Field(
        default=None, 
        description="For single file mode, provide the desired filename for the attachment."
    )
    file_content: Optional[str] = Field(
        default=None, 
        description="For single file mode, provide the content of the file as a single string."
    )

    @field_validator('ticket_key')
    def check_key_format(cls, v: str) -> str:
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
            raise ValueError(f"'{v}' does not appear to be a valid Jira key format (e.g., PROJ-123).")
        return v

    @model_validator(mode='after')
    def check_exclusive_modes(self) -> 'JiraAttachFileSchema':
        """Validate that either batch mode or single file mode is used, but not both."""
        is_batch_mode = self.attachments is not None
        is_single_mode = self.filename is not None or self.file_content is not None

        if is_batch_mode and is_single_mode:
            raise ValueError("Cannot use 'attachments' for batch mode and 'filename'/'file_content' for single mode in the same call. Please use one mode only.")
        
        if not is_batch_mode and not is_single_mode:
            raise ValueError("You must provide either 'attachments' for batch mode or both 'filename' and 'file_content' for single file mode.")

        if is_single_mode and not (self.filename and self.file_content is not None):
            raise ValueError("For single file mode, both 'filename' and 'file_content' are required.")
            
        if is_batch_mode and not self.attachments:
            raise ValueError("For batch mode, the 'attachments' list cannot be empty.")

        return self


# --- CrewAI Tool Definition ---

class JiraAttachFileTool(BaseTool):
    name: str = "attach_file_to_jira_ticket"
    description: str = (
        "Attaches one or more files to a specified Jira ticket. This tool supports two modes, which are mutually exclusive:\n\n"
        "1. **Single File Mode:** Attaches one file. Use the `filename` and `file_content` arguments.\n"
        "   - Example Action Input: `{\"filename\": \"report.txt\", \"file_content\": \"This is the report.\"}`\n\n"
        "2. **Batch Mode:** Attaches multiple files in one operation. Use the `attachments` argument with a list of file dictionaries. Each dictionary must contain 'filename' and 'file_content' keys.\n"
        "   - Example Action Input: `{\"attachments\": [{\"filename\": \"report.md\", \"file_content\": \"## Report\"}, {\"filename\": \"data.csv\", \"file_content\": \"col1,col2\"}]}`"
    )
    args_schema: Type[JiraAttachFileSchema] = JiraAttachFileSchema
    
    allowed_project_prefixes: Optional[List[str]] = Field(
        default=None,
        description="Optional list of allowed project key prefixes to work on (e.g., ['PROJA-', 'PROJB-']). If provided, the tool will only operate on tickets with these prefixes.",
    )
    
    # This is a Pydantic field and it's required because it has no default
    # and is not Optional. It must be present in the kwargs passed to __init__.
    jira_client: JIRA 

    def __init__(self, **kwargs: Any):
        """Initializes the tool with a Jira client and optional allowed_project_prefixes."""
        super().__init__(**kwargs)
        if getattr(self, 'jira_client', None) is None:
             raise ValueError("JiraAttachFileTool requires an initialized JIRA client to be passed via keyword arguments.")

    def _run(
        self, 
        ticket_key: str, 
        attachments: Optional[List[Dict[str, str]]] = None, 
        filename: Optional[str] = None, 
        file_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """The main execution method that handles both single and batch attachments."""
        if self.allowed_project_prefixes and not any(ticket_key.startswith(prefix) for prefix in self.allowed_project_prefixes):
            error_msg = f"Operation on ticket '{ticket_key}' is not allowed. This tool is restricted to projects with the following prefixes: {self.allowed_project_prefixes}."
            print(f"Validation Error: {error_msg}")
            return {"error": error_msg, "status": "Failed Validation - Project"}

        # Normalize input into a list of attachments to process
        attachments_to_process = attachments if attachments is not None else [{'filename': filename, 'file_content': file_content}]

        successful_attachments = []
        failed_attachments = {}

        # Verify ticket exists once before starting the loop
        try:
            print(f"Verifying ticket '{ticket_key}' exists before batch attachment...")
            self.jira_client.issue(ticket_key, fields='id')
            print(f"Target ticket {ticket_key} found.")
        except JIRAError as e:
            error_msg = f"Failed to verify target ticket '{ticket_key}'. API Error: {e.status_code} - {e.text}"
            print(f"Error: {error_msg}")
            return {'error': error_msg, 'status': 'Failed Validation - Ticket'}

        # Process each attachment in the list
        for item in attachments_to_process:
            item_filename = item.get('filename')
            item_content = item.get('file_content')
            
            if not item_filename or item_content is None:
                failed_attachments[f"Unknown File (missing data)"] = "Item in list was missing 'filename' or 'file_content'."
                continue

            try:
                print(f"Preparing to attach '{item_filename}' to {ticket_key}...")
                file_bytes = item_content.encode('utf-8')
                file_like_object = io.BytesIO(file_bytes)
                
                self.jira_client.add_attachment(
                    issue=ticket_key,
                    attachment=file_like_object,
                    filename=item_filename
                )
                successful_attachments.append(item_filename)
                print(f"Successfully attached '{item_filename}'.")

            except JIRAError as e:
                error_detail = f"API Error: {e.status_code} - {e.text}"
                failed_attachments[item_filename] = error_detail
                print(f"Failed to attach '{item_filename}': {error_detail}")
            except Exception as e:
                error_detail = f"Unexpected Error: {str(e)}"
                failed_attachments[item_filename] = error_detail
                print(f"Failed to attach '{item_filename}': {error_detail}")

        # Compile and return a final report for the batch operation
        final_status = "Success"
        if failed_attachments:
            final_status = "Partial Success" if successful_attachments else "Failed"
            
        final_message = f"Batch attachment to ticket {ticket_key} complete. {len(successful_attachments)} succeeded, {len(failed_attachments)} failed."
        print(final_message)

        return {
            "status": final_status,
            "message": final_message,
            "successful_files": successful_attachments,
            "failed_files": failed_attachments
        }


# --- CLI Test Runner ---

def main():
    """Main function to run the tool from the command line."""
    parser = argparse.ArgumentParser(
        description="Test the JiraAttachFileTool from the command line.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("ticket_key", help="The Jira ticket key (e.g., 'PROJ-123').")

    parser.add_argument(
        "--prefixes",
        nargs='+',
        metavar='PREFIX',
        help="Optional: A space-separated list of allowed project key prefixes (e.g., --prefixes PROJ- TEST-)."
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--single", 
        nargs=2, 
        metavar=('FILENAME', 'CONTENT'),
        help="Single file mode. Provide a filename and the content as a string."
    )
    mode_group.add_argument(
        "--batch",
        nargs=2,
        metavar=('FILENAME', 'CONTENT'),
        action='append',
        help="Batch file mode. Can be used multiple times. E.g., --batch f1.txt 'c1' --batch f2.txt 'c2'"
    )

    args: argparse.Namespace = parser.parse_args()

    # Load Jira credentials from .env file
    load_dotenv(override=True)
    try:
        jira_instance_url = os.environ["JIRA_INSTANCE_URL"]
        jira_username = os.environ["JIRA_USERNAME"]
        jira_api_token = os.environ["JIRA_API_TOKEN"]
    except KeyError as e:
        print(f"Error: Environment variable {e} not found. Please create a .env file with your Jira credentials.")
        return

    # Initialize Jira client
    try:
        print(f"Connecting to Jira at {jira_instance_url}...")
        jira_client = JIRA(server=jira_instance_url, basic_auth=(jira_username, jira_api_token))
        print("Successfully connected to Jira.")
    except JIRAError as e:
        print(f"Failed to connect to Jira. Error: {e.status_code} - {e.text}")
        return

    # Instantiate the tool, passing the prefixes if provided
    tool = JiraAttachFileTool(
        jira_client=jira_client,
        allowed_project_prefixes=args.prefixes  # This will be None if the flag is not used
    )
    
    if args.prefixes:
        print(f"Tool instantiated with project prefix restriction: {args.prefixes}")
    
    tool_kwargs = {"ticket_key": args.ticket_key}
    
    # Prepare arguments for the tool's _run method
    if args.single:
        tool_kwargs['filename'] = args.single[0]
        tool_kwargs['file_content'] = args.single[1]
        print(f"\n--- Running in Single File Mode ---")
    
    elif args.batch:
        tool_kwargs['attachments'] = [{'filename': item[0], 'file_content': item[1]} for item in args.batch]
        print(f"\n--- Running in Batch Mode with {len(args.batch)} files ---")

    # Execute the tool and print the result
    result = tool._run(**tool_kwargs)
    
    print("\n--- Tool Execution Report ---")
    print(json.dumps(result, indent=4))
    print("-----------------------------\n")

if __name__ == "__main__":
    # Example Usage:
    #
    # 1. Ensure you have a .env file in your project root with:
    #    JIRA_INSTANCE_URL="https://your-domain.atlassian.net"
    #    JIRA_USERNAME="your-email@example.com"
    #    JIRA_API_TOKEN="your-api-token"
    #
    # 2. Run from the command line from your project's root directory:
    #
    #    Single File Mode:
    #    python ./tools/custom/jira_attach_tool.py PROJ-123 --single "report.txt" "This is the content of the report."
    #
    #    Batch File Mode:
    #    python ./tools/custom/jira_attach_tool.py PROJ-123 --batch "file1.txt" "Content for file 1" --batch "file2.md" "## Markdown Content"
    #
    #    Batch File Mode with Prefix Restriction (will fail if ticket is not in PROJ or TEST):
    #    python ./tools/custom/jira_attach_tool.py OTHER-456 --batch "file.txt" "content" --prefixes PROJ- TEST-
    #
    main()
