import os
from crewai.tools import BaseTool
from atlassian import Confluence

class ConfluenceDataQueryTool(BaseTool):
    """A tool that fetches data from a Confluence page and processes it using the Atlassian Python API."""
    name: str = "ConfluenceDataQueryTool"
    description: str = (
        "This tool fetches the content of a Confluence page by page ID or search results using CQL, "
        "and processes it for further use. The 'input_value' should be either a page id (just the number), or the CQL query."
    )

    class Config:
        arbitrary_types_allowed = True

    def __init__(self):
        super().__init__()


    def _run(self, input_value: str) -> dict:
        """Use the ConfluenceDataQueryTool to fetch either a Confluence page content or search results.
        Fetches data from Confluence using a page id or CQL query.
        
        Args:
            cql_query (str): The CQL query string.
        
        Returns:
            dict: The search results from Confluence in case input is CQL query, or
            string: The content of the page in case input is page id
        """
        if input_value.isdigit():
            return self.fetch_page_content(input_value)
        else:
            return self.fetch_confluence_data(input_value)

    def fetch_confluence_data(self, cql_query: str) -> dict:
        """
        Fetches data from Confluence using a CQL query.
        
        Args:
            cql_query (str): The CQL query string.
        
        Returns:
            dict: The search results from Confluence.
        
        Raises:
            RuntimeError: If there are issues with the API request.
        """
        try:
            confluence_url = os.getenv("CONFLUENCE_ENDPOINT")
            confluence_user = os.getenv("CONFLUENCE_API_USER")
            confluence_token = os.getenv("CONFLUENCE_API_TOKEN")

            if not all([confluence_url, confluence_user, confluence_token]):
                raise ValueError("Missing required Confluence environment variables.")

            confluence = Confluence(
                url=confluence_url,
                username=confluence_user,
                password=confluence_token
            )
            response = confluence.cql(cql_query)
            return response
        except Exception as e:
            raise RuntimeError(f"Failed to fetch data from Confluence: {str(e)}")

    def fetch_page_content(self, page_id: str) -> str:
        """
        Fetches the content of a Confluence page by page ID.
        
        Args:
            page_id (str): The Confluence page ID.
        
        Returns:
            str: The page content.
        
        Raises:
            RuntimeError: If there are issues with the API request.
        """
        try:
            confluence_url = os.getenv("CONFLUENCE_ENDPOINT")
            confluence_user = os.getenv("CONFLUENCE_API_USER")
            confluence_token = os.getenv("CONFLUENCE_API_TOKEN")

            if not all([confluence_url, confluence_user, confluence_token]):
                raise ValueError("Missing required Confluence environment variables.")

            confluence = Confluence(
                url=confluence_url,
                username=confluence_user,
                password=confluence_token
            )

            response = confluence.get_page_by_id(page_id, expand='body.storage')
            return response.get("body", {}).get("storage", {}).get("value", "No content found.")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page content from Confluence: {str(e)}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    tool = ConfluenceDataQueryTool()
    search_result = tool._run('space = "MYSPACE"')
    print(search_result)
    
    page_content = tool._run('123456789')
    print(page_content)
