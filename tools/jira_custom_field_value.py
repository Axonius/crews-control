import requests
import os

def get_jira_custom_field_value(jira_instance_url, user_email, api_token, ticket_key, custom_field_name):
    """
    Fetches the value of a specific custom field from a Jira ticket by its name.

    Args:
        jira_instance_url (str): The base URL of your Jira instance (e.g., "https://your-domain.atlassian.net").
        user_email (str): The email address associated with your Jira account.
        api_token (str): Your Jira API token.
        ticket_key (str): The key of the Jira ticket (e.g., "PROJ-123").
        custom_field_name (str): The name of the custom field to retrieve.

    Returns:
        The value of the custom field, or None if not found or an error occurs.
        The type of the returned value can vary depending on the custom field type
        (e.g., string for a text field, dict for a user or option field).
    """
    api_url = f"{jira_instance_url}/rest/api/3/issue/{ticket_key}?expand=names"

    try:
        response = requests.get(
            api_url,
            auth=(user_email, api_token),
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)

        data = response.json()
        names = data.get("names", {})
        fields = data.get("fields", {})

        # Find the custom field ID from the field name
        custom_field_id = None
        for field_id, field_name in names.items():
            if field_name == custom_field_name:
                custom_field_id = field_id
                break

        if not custom_field_id:
            print(f"Error: Custom field '{custom_field_name}' not found on ticket '{ticket_key}'.")
            return None

        # Retrieve the value using the found custom field ID
        custom_field_value = fields.get(custom_field_id)

        # The structure of the custom field value can vary.
        # For a simple text field, it might be a string.
        # For a dropdown or user picker, it's often a dictionary.
        # This example handles a common case for dropdowns (like the 'Squad' example).
        if isinstance(custom_field_value, dict) and 'value' in custom_field_value:
            return custom_field_value['value']
        else:
            return custom_field_value

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing the Jira response. Missing key: {e}")
        return None


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(override=True)
    # --- Configuration ---
    # It's recommended to use environment variables for sensitive data
    JIRA_INSTANCE_URL = os.environ.get("JIRA_INSTANCE_URL", "https://your-domain.atlassian.net")
    JIRA_USERNAME = os.environ.get("JIRA_USERNAME", "your-email@example.com")
    JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "YOUR_API_TOKEN")

    TICKET_KEY = "PROJ-123"  # Replace with your ticket key
    CUSTOM_FIELD_TO_FETCH = "CustomFieldName"  # Replace with the name of your custom field

    # --- Fetch the value ---
    custom_field_value = get_jira_custom_field_value(
        JIRA_INSTANCE_URL,
        JIRA_USERNAME,
        JIRA_API_TOKEN,
        TICKET_KEY,
        CUSTOM_FIELD_TO_FETCH
    )

    if custom_field_value:
        print(f"The value of the '{CUSTOM_FIELD_TO_FETCH}' field for ticket '{TICKET_KEY}' is: {custom_field_value}")
    else:
        print(f"Failed to retrieve the value for the '{CUSTOM_FIELD_TO_FETCH}' field.")
