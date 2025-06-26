from jira import JIRA
from dotenv import load_dotenv
import os
import math
from tqdm import tqdm
from datetime import datetime
import argparse

# ---- Config ----
load_dotenv(override=True)
JIRA_INSTANCE_URL = os.getenv("JIRA_INSTANCE_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PAGE_SIZE = 100

def find_jira_user_ids(jira_connection, search_string):
    """
    Searches for Jira users by email or display name and lists their details.
    """
    print(f"\nSearching for Jira users matching: '{search_string}'...")
    try:
        # The 'query' parameter is generally used for Jira Cloud.
        # For Jira Server, you might need to adjust or use a different method if this doesn't work as expected.
        # MaxResults is limited to avoid overly large responses.
        users_found = jira_connection.search_users(query=search_string, maxResults=20)

        if not users_found:
            print(f"No users found matching '{search_string}'.")
            return

        print("\nFound the following users (max 20 results):")
        for user_obj in users_found:
            # The user_obj can be a User resource or a dict-like object
            # We try to access attributes; for dicts, it would be user_obj['key']
            
            display_name = "N/A"
            account_id = "N/A"
            email_address = "N/A"
            username_server = "N/A" # Typically 'name' attribute on server

            if hasattr(user_obj, 'displayName'):
                display_name = user_obj.displayName
            if hasattr(user_obj, 'accountId'): # Common for Jira Cloud
                account_id = user_obj.accountId
            if hasattr(user_obj, 'emailAddress'):
                email_address = user_obj.emailAddress
            if hasattr(user_obj, 'name') and account_id == "N/A": # 'name' is often the username on Server
                username_server = user_obj.name


            print(f"  - Display Name : {display_name}")
            print(f"    Account ID   : {account_id} " + ("(Crucial for changelog script)" if account_id != "N/A" else "(Not found, might be Jira Server user or different structure)"))
            print(f"    Email        : {email_address}")
            if username_server != "N/A" and account_id == "N/A":
                 print(f"    Username (Jira Server style): {username_server}")
            print("    ------------------------------------")

        if not any(hasattr(u, 'accountId') for u in users_found):
            print("\nNote: If 'Account ID' is consistently 'N/A', you might be on Jira Server.")
            print("For Jira Server, the 'Username' (often the 'name' attribute) might be used in some contexts, but this script primarily uses Account ID for changelogs.")

    except Exception as e:
        print(f"An error occurred while searching for users: {e}")
        print("Details: The `search_users` functionality and available user attributes can differ between Jira Cloud and Jira Server.")
        print("Ensure your JIRA_USERNAME has user Browse permissions.")


def fetch_and_process_jira_changelogs(jira_connection, project_name_arg, target_user_account_id):
    """
    Fetches Jira issues for a given project, filters their changelogs
    by a target user Account ID, and prints the relevant changes.
    """
    jql_query = f'project = "{project_name_arg}" AND updated >= -30d ORDER BY updated DESC'

    print(f"\nSearching Jira for issues in project '{project_name_arg}' with updates in the past 30 days.")
    print(f"Targeting user account ID: {target_user_account_id}")

    # ---- Initial Fetch (Page 0) ----
    print("\nFetching first page to determine total size...")
    try:
        initial_issues = jira_connection.search_issues(
            jql_query,
            startAt=0,
            maxResults=PAGE_SIZE,
            expand='changelog',
            fields='summary,key,reporter'
        )
        if not initial_issues:
            print(f"✅ No issues found matching the query for project '{project_name_arg}'.")
            return

        total_issues = initial_issues.total
        total_pages = math.ceil(total_issues / PAGE_SIZE)
        print(f"✅ Found {total_issues} issues in total for project '{project_name_arg}', across {total_pages} pages.")

    except Exception as e:
        print(f"An error occurred during the initial fetch: {e}")
        exit(1) # Critical error, exit

    # ---- Fetch Remaining Pages with a Progress Bar ----
    all_issues = list(initial_issues)

    if total_pages > 1:
        with tqdm(total=total_issues, initial=len(all_issues), desc="Fetching Jira Issues", unit=" issue") as pbar:
            for page_num in range(1, total_pages):
                start_at = page_num * PAGE_SIZE
                try:
                    issues = jira_connection.search_issues(
                        jql_query,
                        startAt=start_at,
                        maxResults=PAGE_SIZE,
                        expand='changelog',
                        fields='summary,key,reporter'
                    )
                    all_issues.extend(issues)
                    pbar.update(len(issues))
                except Exception as e:
                    print(f"\nAn error occurred while fetching page {page_num + 1}: {e}")
                    break

    print(f"\nTotal issues successfully fetched: {len(all_issues)}")

    # ---- Process and Display Changes by Target User ----
    print(f"\nProcessing changes made by user: {target_user_account_id}\n")

    issues_with_target_updates = 0
    if not all_issues:
        print(f"No issues were fetched or available for project '{project_name_arg}'.")
    else:
        for issue in all_issues:
            has_printed_issue_header = False
            if not hasattr(issue, 'changelog') or not issue.changelog:
                continue

            for history in issue.changelog.histories:
                if hasattr(history.author, 'accountId') and history.author.accountId == target_user_account_id:
                    if not has_printed_issue_header:
                        print("--------------------------------------------------")
                        print(f"Issue: {issue.key} - {issue.fields.summary}")
                        reporter_name = "Not available or anonymous"
                        if hasattr(issue.fields.reporter, 'displayName'):
                            reporter_name = issue.fields.reporter.displayName
                        elif hasattr(issue.fields.reporter, 'name'): # Fallback for Jira Server like reporter
                             reporter_name = issue.fields.reporter.name
                        print(f"Reporter: {reporter_name}")
                        has_printed_issue_header = True
                        issues_with_target_updates += 1

                    try:
                        timestamp = datetime.strptime(history.created, '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y-%m-%d %H:%M:%S %Z')
                    except ValueError:
                        timestamp = history.created

                    author_display_name = "Unknown User"
                    if hasattr(history.author, 'displayName'):
                        author_display_name = history.author.displayName
                    elif hasattr(history.author, 'name'): # Fallback for Jira Server like author
                        author_display_name = history.author.name
                    print(f"\n  -> Update by {author_display_name} on {timestamp}")

                    for item in history.items:
                        field_name = item.field.capitalize()
                        from_str = item.fromString if hasattr(item, 'fromString') and item.fromString is not None else "nothing"
                        to_str = item.toString if hasattr(item, 'toString') and item.toString is not None else "nothing"
                        
                        if from_str == '': from_str = 'nothing'
                        if to_str == '': to_str = 'nothing'

                        print(f"     - Field '{field_name}' changed from '{from_str}' to '{to_str}'")
            if has_printed_issue_header:
                print("--------------------------------------------------\n")

    if issues_with_target_updates == 0:
        print(f"No issues were found with updates by the user account ID '{target_user_account_id}' in project '{project_name_arg}' within the last 30 days.")
    else:
        print(f"Found {issues_with_target_updates} issues with changes by the target user account ID '{target_user_account_id}' in project '{project_name_arg}'.")

    print("\nScript finished.")

# ---- Script Entry Point ----
if __name__ == "__main__":
    # ---- Argument Parsing ----
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Jira issue changelogs for a specific project and filter by a user's Account ID. "
            "Alternatively, find a user's Account ID by email or display name."
        ),
        formatter_class=argparse.RawTextHelpFormatter, # Allows for better formatting of help
        epilog=(
            "Examples:\n"
            "  To find a user's ID:\n"
            "    python %(prog)s --find-user-id \"jane.doe@example.com\"\n"
            "    python %(prog)s --find-user-id \"Jane Doe\"\n\n"
            "  To fetch changelogs for a user in a project:\n"
            "    python %(prog)s MYPROJECT 712020:233b9d7e-52f1-4bcd-984e-6852711e9ae0\n"
            "    python %(prog)s \"My Awesome Project\" 5f9c1b9b8f7c6d006e7b1a2d"
        )
    )
    parser.add_argument(
        "--find-user-id",
        type=str,
        metavar="EMAIL_OR_NAME",
        help="Find Jira user Account ID by email or display name and exit. \nIf used, project_name and account_id arguments are ignored."
    )
    # Positional arguments, only required if --find-user-id is not used
    parser.add_argument(
        "project_name",
        type=str,
        nargs='?', # Makes it optional at parser level
        default=None,
        help="The name or key of the Jira project (e.g., 'PROJA'). Required if not using --find-user-id."
    )
    parser.add_argument(
        "account_id",
        type=str,
        nargs='?', # Makes it optional at parser level
        default=None,
        help="The Atlassian Account ID of the target user. Required if not using --find-user-id."
    )

    args = parser.parse_args()

    # ---- Determine Action and Validate Arguments BEFORE Connecting to Jira ----
    action_to_perform = None
    if args.find_user_id:
        action_to_perform = "find_user"
    elif args.project_name and args.account_id:
        action_to_perform = "fetch_changelogs"
    else:
        # This case handles when no arguments are given, or only one of project_name/account_id is given
        # without --find-user-id
        parser.error(
            "Insufficient arguments. Provide either --find-user-id OR both project_name and account_id.\n"
            "Run with -h for more details."
        )

    # ---- Pre-flight Checks for Jira Credentials ----
    if not all([JIRA_INSTANCE_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
        print("Error: JIRA_INSTANCE_URL, JIRA_USERNAME, or JIRA_API_TOKEN environment variables are not set.")
        print("Please ensure you have a .env file with these values or they are set in your environment.")
        exit(1)

    # ---- Establish Jira Connection (once) ----
    jira_conn = None
    try:
        print("Attempting to connect to Jira...")
        jira_conn = JIRA(server=JIRA_INSTANCE_URL, basic_auth=(JIRA_USERNAME, JIRA_API_TOKEN), timeout=60)
        jira_conn.myself() # Test connection
        print("✅ Successfully connected to Jira.")
    except Exception as e:
        print(f"Failed to connect to Jira: {e}")
        print("Please check your JIRA_INSTANCE_URL, JIRA_USERNAME, JIRA_API_TOKEN, and network connectivity.")
        exit(1)

    # ---- Main Logic ----
    if args.find_user_id:
        find_jira_user_ids(jira_conn, args.find_user_id)
    else:
        # If --find-user-id is not used, project_name and account_id become mandatory
        if not args.project_name or not args.account_id:
            parser.error(
                "The following arguments are required when not using --find-user-id: project_name, account_id\n"
                "Run with -h for more details."
            )
        fetch_and_process_jira_changelogs(jira_conn, args.project_name, args.account_id)
