import os
from crewai_tools import BaseTool
from utils import get_embedchain_settings
from embedchain import App

class WebsiteContentQueryTool(BaseTool):
    """A tool that fetches website content, adds it to a vector database, and queries it."""
    name: str = "WebsiteContentQueryTool"
    description: str = (
        "This tool fetches the content of a website, adds it to a vector database, and queries the vector database for a given query string."
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _run(self, url: str, query: str) -> str:
        """Use the WebsiteContentQueryTool."""
        return self.query_website_content(url=url, query=query)

    def query_website_content(self, url: str, query: str) -> str:
        """
        Fetches the content of a website, adds it to a vector database, and queries the vector database for a given query string.

        Parameters:
        url (str): The URL of the website to fetch content from.
        query (str): The query string to search in the vector database.

        Returns:
        str: The result from the vector database query.

        Raises:
        Exception: If there is an issue with fetching website content or querying the vector database.
        """
        # Fetch the content of the website
        try:
            config = get_embedchain_settings(task_id='shared')
            app = App.from_config(config=config)
            app.add(url, data_type='web_page')
        except Exception as e:
            raise Exception(f"Failed to fetch website content: {e}")

        # Query the vector database
        try:
            results = app.query(query)
        except Exception as e:
            raise Exception(f"Failed to query vector database: {e}")

        # Return the result from the vector database
        return str(results)
