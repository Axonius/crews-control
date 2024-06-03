import os
from crewai_tools import BaseTool
from utils import get_embedchain_settings
from embedchain import App
from typing import Optional

class WebsiteContentQueryTool(BaseTool):
    """A tool that fetches website content, adds it to a vector database, and queries it."""
    name: str = "WebsiteContentQueryTool"
    app: Optional[App] = None
    description: str = (
        "This tool fetches the content of a website, adds it to a vector database, and queries the vector database for a given query string."
    )
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, app: 'App', **kwargs):
        super().__init__(**kwargs)
        if app and isinstance(app, App):
            self.app = app

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
            if not self.app:
                config = get_embedchain_settings(task_id='shared',
                                                 llm_name=os.getenv('LLM_NAME'),
                                                 embedder_name=os.getenv('EMBEDDER_NAME'))
                self.app = App.from_config(config=config)
            self.app.add(url, data_type='web_page')
            results = self.app.query(query)
        except Exception as e:
            raise Exception(f"Failed to fetch website content: {e}")

        # Return the result from the vector database
        return str(results)
