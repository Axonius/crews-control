# --- Necessary Imports ---
import os
import base64
import requests
import logging # Use standard logging
import http.client # Keep for optional debugging setup
from io import BytesIO
from typing import Dict, Literal, Optional, Type, Any, Tuple, List
from pydantic import BaseModel, Field, field_validator, model_validator, SecretStr, HttpUrl, ConfigDict
from urllib.parse import urlparse

# CrewAI Imports
from crewai.tools.base_tool import BaseTool
from crewai.utilities import I18N
# Keep CrewAI core imports for the example usage section
from crewai import Agent, Task, Crew, Process, LLM

# --- Conditional Imports & Library Availability Checks ---
# These checks help manage optional dependencies gracefully.

try:
    from jira import JIRA, JIRAError
    JIRA_AVAILABLE = True
except ImportError:
    JIRA_AVAILABLE = False
    class JIRAError(Exception): pass # Define dummy for except blocks

try:
    from atlassian import Confluence
    CONFLUENCE_AVAILABLE = True
except ImportError:
    CONFLUENCE_AVAILABLE = False

try:
    import openai
    # Define dummy exceptions if openai < 1.0 or not installed
    if not hasattr(openai, "AzureOpenAI"): raise ImportError("Requires openai>=1.0.0")
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    class OpenAIError(Exception): pass
    # Define dummy exceptions to avoid NameErrors later if library missing
    class APIConnectionError(OpenAIError): pass
    class RateLimitError(OpenAIError): pass
    class APIStatusError(OpenAIError):
        def __init__(self, status_code=None, response=None):
            self.status_code = status_code
            self.response = response
            super().__init__(f"Status={status_code}, Response={response}")
    # Make openai module accessible even if import failed, to avoid NameErrors
    class DummyOpenAI:
        APIConnectionError = APIConnectionError
        RateLimitError = RateLimitError
        APIStatusError = APIStatusError
    if 'openai' not in locals():
        openai = DummyOpenAI()


try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

# --- Setup Logging ---
# Configure logging level (e.g., INFO, DEBUG) as needed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Logger for this module

# Optional: Quieten overly verbose libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# --- Optional HTTP Debugging ---
# Uncomment to enable detailed HTTP request/response logging
# http.client.HTTPConnection.debuglevel = 1
# logging.getLogger("httpx").setLevel(logging.DEBUG)
# logging.getLogger("httpcore").setLevel(logging.DEBUG)
# logger.info("HTTP Debugging Enabled")


# --- Configuration Models ---
# Use Pydantic for clear, validated configuration structures

class AzureConfig(BaseModel):
    api_key: SecretStr
    endpoint: HttpUrl # Use HttpUrl for validation
    api_version: str
    vision_deployment: str
    client: Optional[Any] = None # Allow passing pre-initialized client

    @model_validator(mode='after')
    def init_client(self) -> 'AzureConfig':
        if self.client is None:
            if not OPENAI_AVAILABLE:
                raise ImportError("Cannot initialize Azure OpenAI client: 'openai' library >= 1.0.0 is required.")
            try:
                logger.info(f"Initializing Azure OpenAI client for endpoint: {self.endpoint} / deployment: {self.vision_deployment}")
                self.client = openai.AzureOpenAI(
                    api_key=self.api_key.get_secret_value(),
                    azure_endpoint=str(self.endpoint), # Convert HttpUrl back to str
                    api_version=self.api_version
                )
                # Add a simple check if possible, e.g., listing models (optional)
                # self.client.models.list()
                logger.info("Azure OpenAI client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI client: {e}", exc_info=True)
                raise ConnectionError(f"Failed to initialize Azure OpenAI client: {e}") from e
        return self


class JiraConfig(BaseModel):
    instance_url: HttpUrl
    username: str
    api_token: SecretStr
    client: Optional[Any] = None # Allow passing pre-initialized client
    domain: Optional[str] = None

    @model_validator(mode='after')
    def derived_fields_and_init(self) -> 'JiraConfig':
        # Derive domain
        self.domain = urlparse(str(self.instance_url)).netloc.lower()

        # Initialize client if not provided
        if self.client is None:
            if not JIRA_AVAILABLE:
                raise ImportError("Cannot initialize Jira client: 'jira' library is required.")
            try:
                logger.info(f"Initializing Jira client for server: {self.instance_url}")
                self.client = JIRA(
                    server=str(self.instance_url),
                    basic_auth=(self.username, self.api_token.get_secret_value()),
                    timeout=30,
                    max_retries=1 # Avoid excessive retries by default
                )
                # Test connection
                self.client.myself()
                logger.info("Jira client initialized successfully.")
            except JIRAError as e:
                logger.error(f"Failed to connect/authenticate to Jira at {self.instance_url}: {e.status_code} {e.text}", exc_info=False) # Don't need full trace for auth errors
                raise ConnectionError(f"Failed to connect/authenticate to Jira at {self.instance_url}: {e.status_code} {getattr(e, 'text', 'Unknown Error')}") from e
            except Exception as e:
                logger.error(f"Unexpected error initializing Jira client for {self.instance_url}: {e}", exc_info=True)
                raise ConnectionError(f"Unexpected error initializing Jira client: {e}") from e
        return self


class ConfluenceConfig(BaseModel):
    endpoint_url: HttpUrl
    username: str
    api_token: SecretStr
    client: Optional[Any] = None # Allow passing pre-initialized client
    domain: Optional[str] = None

    @model_validator(mode='after')
    def derived_fields_and_init(self) -> 'ConfluenceConfig':
        # Derive domain
        self.domain = urlparse(str(self.endpoint_url)).netloc.lower()

        # Initialize client if not provided
        if self.client is None:
            if not CONFLUENCE_AVAILABLE:
                raise ImportError("Cannot initialize Confluence client: 'atlassian-python-api' library is required.")
            try:
                logger.info(f"Initializing Confluence client for URL: {self.endpoint_url}")
                self.client = Confluence(
                    url=str(self.endpoint_url),
                    username=self.username,
                    password=self.api_token.get_secret_value(),
                    timeout=30
                )
                logger.info("Confluence client initialized successfully.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to connect/authenticate to Confluence at {self.endpoint_url}: {e}", exc_info=True)
                raise ConnectionError(f"Failed to connect/authenticate to Confluence: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error initializing Confluence client for {self.endpoint_url}: {e}", exc_info=True)
                raise ConnectionError(f"Unexpected error initializing Confluence client: {e}") from e
        return self

# --- Custom Exceptions for Internal Flow Control ---
class ToolConfigurationError(ValueError):
    """Error related to tool configuration."""
    pass

class ImageFetchError(Exception):
    """Error during image fetching."""
    pass

class VisionApiError(Exception):
    """Error during Vision API call."""
    pass


# --- AMENDED Tool Input Schema ---
# Implements the simplified URI logic while keeping the original class name.
class AdvancedImageAnalyzerSchema(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )
    """Input schema for the AdvancedImageAnalyzerTool."""
    # This is now the ONLY data input besides the prompt.
    # The description is the "manual" for the LLM agent.
    image_references: str = Field(...,
        description="A string containing one or more self-contained image locations, EACH SEPARATED BY A NEWLINE. "
                    "Format each line as follows: "
                    "For a URL, use the full URL (e.g., 'https://...'). "
                    "For Jira, use 'jira://ISSUE_KEY/filename.png'. "
                    "For Confluence, use 'confluence://PAGE_ID/filename.jpg'."
    )
    analysis_prompt: str = Field(..., description="Specific question or instructions for analyzing all images using the vision model.")


# --- Refactored and Optimized Tool ---
class AdvancedImageAnalyzerTool(BaseTool):
    # Kept original name, but updated description for the new format
    name: str = "Advanced Image Analyzer"
    description: str = (
        "Fetches and analyzes multiple images from a newline-separated string of locations. "
        "Each location must be a self-contained URI (e.g., http://..., jira://PROJ-123/file.png, confluence://12345/file.jpg). "
        "Applies the same analysis prompt to each image."
    )
    args_schema: type[BaseModel] = AdvancedImageAnalyzerSchema

    # Configuration stored from init
    _azure_config: Optional[AzureConfig] = None
    _jira_config: Optional[JiraConfig] = None
    _confluence_config: Optional[ConfluenceConfig] = None

    def __init__(
        self,
        azure_config: AzureConfig, # Require Azure config for analysis
        jira_config: Optional[JiraConfig] = None,
        confluence_config: Optional[ConfluenceConfig] = None,
        **kwargs
    ):
        """
        Initializes the tool with necessary configurations.

        Args:
            azure_config: Configuration for Azure OpenAI Vision API.
            jira_config: Optional configuration for Jira access. Required if analyzing Jira attachments.
            confluence_config: Optional configuration for Confluence access. Required if analyzing Confluence attachments.
        """
        super().__init__(**kwargs)

        self._logger = logging.getLogger(__name__ + ".AdvancedImageAnalyzerTool") # Instance logger
        self._logger.info("Initializing AdvancedImageAnalyzerTool...")

        # --- Validate and Store Configurations ---
        if not isinstance(azure_config, AzureConfig) or not azure_config.client:
             # Client initialization happens within AzureConfig validation
             raise ToolConfigurationError("Valid AzureConfig with initialized client is required.")
        self._azure_config = azure_config
        self._logger.info("Azure configuration loaded.")

        if jira_config:
             if not JIRA_AVAILABLE:
                  raise ToolConfigurationError("JiraConfig provided, but 'jira' library is not installed.")
             if not isinstance(jira_config, JiraConfig) or not jira_config.client:
                  raise ToolConfigurationError("Valid JiraConfig with initialized client is required when provided.")
             self._jira_config = jira_config
             self._logger.info("Jira configuration loaded.")
        else:
             self._logger.warning("Jira configuration not provided. Analyzing Jira attachments will not be possible.")


        if confluence_config:
             if not CONFLUENCE_AVAILABLE:
                  raise ToolConfigurationError("ConfluenceConfig provided, but 'atlassian-python-api' library is not installed.")
             if not isinstance(confluence_config, ConfluenceConfig) or not confluence_config.client:
                  raise ToolConfigurationError("Valid ConfluenceConfig with initialized client is required when provided.")
             self._confluence_config = confluence_config
             self._logger.info("Confluence configuration loaded.")
        else:
             self._logger.warning("Confluence configuration not provided. Analyzing Confluence attachments will not be possible.")

        self._logger.info("AdvancedImageAnalyzerTool initialized successfully.")


    # --- Private Helper Methods ---

    def _get_auth_for_url(self, url: str) -> Optional[Tuple[str, str]]:
        """Determine if URL matches configured Jira/Confluence and return auth tuple."""
        try:
            target_domain = urlparse(url).netloc.lower()
            if not target_domain: return None

            # Check Jira
            if self._jira_config and self._jira_config.domain == target_domain:
                 self._logger.debug(f"URL domain '{target_domain}' matches configured Jira domain. Using Jira auth.")
                 return (self._jira_config.username, self._jira_config.api_token.get_secret_value())

            # Check Confluence
            if self._confluence_config and self._confluence_config.domain == target_domain:
                 self._logger.debug(f"URL domain '{target_domain}' matches configured Confluence domain. Using Confluence auth.")
                 return (self._confluence_config.username, self._confluence_config.api_token.get_secret_value())

            return None # No match or no auth configured for matched domain
        except Exception as e:
            self._logger.warning(f"Failed to parse domain or get auth for URL '{url}': {e}", exc_info=False)
            return None

    def _download_from_url(self, url: str) -> bytes:
        """Downloads image content from a URL, potentially using auth."""
        self._logger.info(f"Downloading image from URL: {url}")
        auth = self._get_auth_for_url(url)
        try:
            headers = {
                'Accept': 'image/png, image/jpeg, image/gif, image/webp, application/octet-stream, */*',
                'User-Agent': 'CrewAI-AdvancedImageAnalyzerTool/2.0'
            }
            # Use timeout and stream for potentially large files
            response = requests.get(url, stream=True, timeout=30, auth=auth, headers=headers)
            response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)

            image_bytes = response.content
            if not image_bytes:
                raise ValueError("Downloaded content was empty.")

            self._logger.info(f"Downloaded {len(image_bytes)} bytes from URL.")
            return image_bytes

        except requests.exceptions.Timeout:
             self._logger.error(f"Timeout error downloading image from URL {url}")
             raise ImageFetchError(f"Timeout error downloading image from URL {url}")
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Network error downloading image from URL {url}: {e}", exc_info=True)
            # Provide specific feedback for common errors if possible
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 404:
                 raise ImageFetchError(f"Image not found at URL (404): {url}")
            if status_code == 401 or status_code == 403:
                 raise ImageFetchError(f"Authentication/Authorization error downloading from URL (Status {status_code}): {url}")
            raise ImageFetchError(f"Network error downloading image from URL {url}: {e}") from e
        except ValueError as e:
             self._logger.error(f"Value error during URL download {url}: {e}")
             raise ImageFetchError(f"Failed to process download from {url}: {e}") from e


    def _fetch_from_jira(self, issue_key: str, filename: str) -> bytes:
        """Fetches an image attachment from Jira."""
        if not self._jira_config or not self._jira_config.client:
            raise ToolConfigurationError("Jira is not configured for this tool instance.")

        jira = self._jira_config.client
        self._logger.info(f"Searching for Jira attachment '{filename}' in issue '{issue_key}'...")
        try:
            # Fetch only necessary fields
            issue = jira.issue(issue_key, fields='attachment')
            found_attachment = next((att for att in issue.fields.attachment if att.filename == filename), None)

            if found_attachment:
                self._logger.info(f"Found Jira attachment '{filename}'. Downloading...")
                image_bytes = found_attachment.get()
                if not image_bytes:
                    raise ValueError("Downloaded Jira attachment content was empty.")
                self._logger.info(f"Downloaded {len(image_bytes)} bytes from Jira attachment.")
                return image_bytes
            else:
                self._logger.warning(f"Jira attachment '{filename}' not found in issue '{issue_key}'.")
                raise ImageFetchError(f"Jira attachment '{filename}' not found in issue '{issue_key}'.")

        except JIRAError as e:
            self._logger.error(f"Jira API error fetching issue/attachment {issue_key}/{filename}: {e.status_code} {e.text}", exc_info=False)
            if e.status_code == 404:
                 raise ImageFetchError(f"Jira issue '{issue_key}' not found or attachment '{filename}' not found.")
            raise ImageFetchError(f"Jira API error for {issue_key}/{filename}: {e.status_code} {getattr(e, 'text', 'Unknown')}") from e
        except Exception as e:
            self._logger.error(f"Unexpected error fetching Jira attachment {issue_key}/{filename}: {e}", exc_info=True)
            raise ImageFetchError(f"Unexpected error fetching Jira attachment: {e}") from e


    def _fetch_from_confluence(self, page_id: str, filename: str) -> bytes:
        """Fetches an image attachment from Confluence."""
        if not self._confluence_config or not self._confluence_config.client:
            raise ToolConfigurationError("Confluence is not configured for this tool instance.")

        confluence = self._confluence_config.client
        self._logger.info(f"Searching for Confluence attachment '{filename}' on page '{page_id}'...")
        # Unescape filename
        import html
        filename = html.unescape(filename)
        try:
            # Use expand to potentially avoid extra calls, though content might not be needed here
            attachments_result = confluence.get_attachments_from_content(page_id=page_id, limit=200, filename=filename) # Filter by filename if API supports it
            attachments = attachments_result.get('results', [])

            # If filename filter worked, there should be 0 or 1 result
            if attachments:
                 found_attachment_info = attachments[0]
                 # Double check filename in case API filter is unreliable
                 if found_attachment_info['title'] == filename:
                    attachment_id = found_attachment_info['id']
                    self._logger.info(f"Found Confluence attachment '{filename}' (ID: {attachment_id}). Downloading...")
                    download_link = found_attachment_info['_links']['download']
                    full_download_url = confluence.url + download_link
                    response = requests.get(full_download_url, auth=(confluence.username, confluence.password))
                    if response.status_code == 200:
                        image_bytes = response.content
                    else:
                        raise ValueError("Downloaded Confluence attachment content was empty.")
                    self._logger.info(f"Downloaded {len(image_bytes)} bytes from Confluence attachment.")
                    return image_bytes
                 else:
                    # This case should be rare if filename filter works
                    self._logger.warning(f"Confluence API returned attachment, but title mismatch ('{found_attachment_info['title']}' != '{filename}')")
                    raise ImageFetchError(f"Confluence attachment filter mismatch for '{filename}' on page '{page_id}'.")
            else:
                # Try without filename filter as fallback (more expensive)
                self._logger.info(f"Attachment '{filename}' not found via filename filter, checking all attachments on page '{page_id}'...")
                attachments_result = confluence.get_attachments_from_content(page_id=page_id, limit=200)
                attachments = attachments_result.get('results', [])
                found_attachment_info = next((att for att in attachments if att['title'] == filename), None)
                if found_attachment_info:
                     attachment_id = found_attachment_info['id']
                     self._logger.info(f"Found Confluence attachment '{filename}' (ID: {attachment_id}) via full list scan. Downloading...")
                     image_bytes = confluence.get_attachment_content(attachment_id=attachment_id)
                     if not image_bytes:
                        raise ValueError("Downloaded Confluence attachment content was empty.")
                     self._logger.info(f"Downloaded {len(image_bytes)} bytes from Confluence attachment.")
                     return image_bytes
                else:
                     self._logger.warning(f"Confluence attachment '{filename}' not found on page '{page_id}'.")
                     raise ImageFetchError(f"Confluence attachment '{filename}' not found on page '{page_id}'.")

        except requests.exceptions.RequestException as e:
            self._logger.error(f"Confluence API error fetching attachment {page_id}/{filename}: {e}", exc_info=True)
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 404:
                raise ImageFetchError(f"Confluence page '{page_id}' not found or attachment '{filename}' not found.")
            raise ImageFetchError(f"Confluence API error for {page_id}/{filename}: {e}") from e
        except Exception as e:
            self._logger.error(f"Unexpected error fetching Confluence attachment {page_id}/{filename}: {e}", exc_info=True)
            raise ImageFetchError(f"Unexpected error fetching Confluence attachment: {e}") from e


    def _fetch_image_bytes(self, image_reference: str, source_id: Optional[str], source_type: Optional[str]) -> bytes:
        """Determines source and fetches image bytes."""
        self._logger.debug(f"Fetching image bytes for ref: '{image_reference}', source: {source_type}/{source_id}")
        is_url = image_reference.lower().startswith(('http://', 'https://'))

        if is_url:
            return self._download_from_url(image_reference)
        else:
            # Context (source_id, source_type) validated by Pydantic schema already
            if source_type == 'jira':
                return self._fetch_from_jira(source_id, image_reference)
            elif source_type == 'confluence':
                return self._fetch_from_confluence(source_id, image_reference)
            else:
                # This case should not be reachable due to Pydantic validation
                 self._logger.error(f"Invalid state: Reached filename processing with invalid source_type '{source_type}'.")
                 raise ToolConfigurationError(f"Invalid source_type '{source_type}' encountered unexpectedly.")


    def _to_base64_data_uri(self, image_bytes: bytes) -> str:
        """
        Converts image bytes to a base64 data URI.
        Raises ValueError if the content is not identified as a supported image type.
        """
        detected_mime = None
        try:
            if MAGIC_AVAILABLE:
                # Use buffer method for bytes
                detected_mime = magic.from_buffer(image_bytes, mime=True)
                self._logger.debug(f"python-magic detected MIME: {detected_mime}")
            else:
                 # Fallback using imghdr (less reliable)
                 # Ensure imghdr is imported if used here, or handle ImportError
                 try:
                     import imghdr
                     img_type = imghdr.what(None, h=image_bytes)
                     detected_mime = f"image/{img_type.lower()}" if img_type else None
                     self._logger.debug(f"imghdr detected type: {img_type}")
                 except ImportError:
                     self._logger.warning("Cannot detect MIME type: 'imghdr' library not found and 'python-magic' is unavailable.")
                     # No reliable detection possible, proceed to check if detected_mime is None below

        except Exception as e:
            # Catch potential errors during MIME detection itself
            self._logger.warning(f"Error during MIME type detection: {e}. Proceeding without confirmed type.", exc_info=False)
            # Let the check below handle the case where detection failed

        # --- Strict Check ---
        # Check if detection succeeded AND resulted in an image MIME type
        if detected_mime and detected_mime.startswith('image/'):
            mime_type = detected_mime
            self._logger.info(f"Confirmed image MIME type: {mime_type}")
        else:
            # If detection failed (detected_mime is None) or resulted in non-image type
            error_message = f"Downloaded content is not a recognized image format (detected type: {detected_mime or 'unknown'}). Cannot proceed with analysis."
            self._logger.error(error_message)
            raise ValueError(error_message) # Raise error to stop processing

        # --- Encoding (only runs if the check above passed) ---
        base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{base64_encoded_data}"
        self._logger.info(f"Encoded image to base64 data URI (MIME: {mime_type}, Length: {len(data_uri)}).")
        return data_uri

    def _call_azure_vision_api(self, data_uri: str, prompt: str) -> str:
        """Calls the configured Azure Vision API."""
        if not self._azure_config or not self._azure_config.client:
             # This should be caught at init, but double-check
             raise ToolConfigurationError("Azure Vision API client is not configured.")

        client = self._azure_config.client
        deployment = self._azure_config.vision_deployment
        self._logger.info(f"Calling Azure Vision API (Deployment: {deployment}). Prompt: '{prompt[:100]}...'")

        try:
            api_response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    }
                ],
                # max_completion_tokens=1500,
            )

            description = api_response.choices[0].message.content
            if not description:
                 self._logger.warning("Received empty description from Vision API.")
                 # Decide if empty response is an error or valid result
                 # raise VisionApiError("Received empty description from Vision API.")
                 return "(Vision API returned an empty description)" # Or return specific string

            self._logger.info("Received description from Vision API successfully.")
            return description.strip()

        except openai.APIConnectionError as e:
             self._logger.error(f"Azure OpenAI connection error: {e}", exc_info=True)
             raise VisionApiError(f"Could not connect to Azure OpenAI: {e}") from e
        except openai.RateLimitError as e:
             self._logger.error(f"Azure OpenAI rate limit exceeded: {e}", exc_info=False)
             raise VisionApiError(f"Azure OpenAI rate limit exceeded. Please try again later.") from e
        except openai.APIStatusError as e:
             self._logger.error(f"Azure OpenAI API error: Status={e.status_code}, Response={e.response}", exc_info=True)
             raise VisionApiError(f"Azure OpenAI API returned an error (Status {e.status_code}). Check deployment name and API key/endpoint.") from e
        except Exception as e:
             self._logger.error(f"Unexpected error during Vision API call: {e}", exc_info=True)
             raise VisionApiError(f"An unexpected error occurred during image analysis: {e}") from e


    # --- Main Execution Method (`_run`) ---
    def _run(
        self,
        image_references: str, # Using original argument name
        analysis_prompt: str,
        **kwargs
    ) -> str:
        """
        Parses the newline-separated string of image references, determines the source
        for each, fetches the image, and performs the analysis.
        """
        references_list = [ref.strip() for ref in image_references.split('\n') if ref.strip()]

        if not references_list:
            return "Error: The 'image_references' string was empty."

        self._logger.info(f"Starting batch analysis for {len(references_list)} images.")
        all_results = []

        for i, reference in enumerate(references_list):
            self._logger.info(f"--- Processing reference {i+1}/{len(references_list)}: '{reference}' ---")
            
            try:
                image_bytes = None
                if reference.lower().startswith(('http://', 'https://')):
                    image_bytes = self._fetch_image_bytes(image_reference=reference, source_id=None, source_type=None)

                elif reference.lower().startswith('jira://'):
                    parts = reference[7:].split('/', 1)
                    if len(parts) != 2 or not parts[0] or not parts[1]:
                        raise ImageFetchError(f"Invalid Jira format. Expected 'jira://KEY/FILENAME', got '{reference}'.")
                    issue_key, filename = parts
                    image_bytes = self._fetch_image_bytes(image_reference=filename, source_id=issue_key, source_type='jira')

                elif reference.lower().startswith('confluence://'):
                    parts = reference[13:].split('/', 1)
                    if len(parts) != 2 or not parts[0] or not parts[1]:
                        raise ImageFetchError(f"Invalid Confluence format. Expected 'confluence://PAGE_ID/FILENAME', got '{reference}'.")
                    page_id, filename = parts
                    image_bytes = self._fetch_image_bytes(image_reference=filename, source_id=page_id, source_type='confluence')
                
                else:
                    raise ImageFetchError(f"Unsupported reference format. Must start with http(s)://, jira://, or confluence://. Got '{reference}'.")

                data_uri = self._to_base64_data_uri(image_bytes)
                del image_bytes
                description = self._call_azure_vision_api(data_uri, analysis_prompt)
                
                self._logger.info(f"Analysis successful for '{reference}'.")
                all_results.append(f"Result for '{reference}':\n{description}")

            except (ImageFetchError, VisionApiError, ToolConfigurationError, ValueError) as e:
                self._logger.error(f"Tool Error during analysis for '{reference}': {e}", exc_info=False)
                all_results.append(f"Result for '{reference}':\nError: {e}")
            except Exception as e:
                self._logger.exception(f"Unexpected critical error during analysis for '{reference}': {e}")
                all_results.append(f"Result for '{reference}':\nError: An unexpected critical error occurred: {type(e).__name__}")
        
        final_output = "\n\n---\n\n".join(all_results)
        self._logger.info("Batch analysis complete.")
        return final_output


# --- Example Usage (Requires CrewAI and necessary env vars) ---

def run_crewai_example():
    """Sets up and runs a CrewAI example using the final, refactored tool."""
    logger.info("\n--- Setting up CrewAI Example ---")

    # --- Load Configuration (This part is unchanged and correct) ---
    try:
        from dotenv import load_dotenv
        if load_dotenv(override=True):
             logger.info("Loaded environment variables from .env file.")
        else:
             logger.info("No .env file found, relying on system environment variables.")

        azure_conf = AzureConfig(
            api_key=os.environ["AZURE_API_KEY"],
            endpoint=os.environ["AZURE_API_BASE"],
            api_version=os.environ["AZURE_API_VERSION"],
            vision_deployment=os.environ["AZURE_OPENAI_VISION_DEPLOYMENT"]
        )

        jira_conf = None
        if JIRA_AVAILABLE and all(k in os.environ for k in ['JIRA_INSTANCE_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN']):
            try:
                jira_conf = JiraConfig(
                    instance_url=os.environ['JIRA_INSTANCE_URL'],
                    username=os.environ['JIRA_USERNAME'],
                    api_token=os.environ['JIRA_API_TOKEN']
                )
            except Exception as e:
                 logger.warning(f"Failed to create JiraConfig: {e}. Jira functionality disabled.")
        else:
             logger.warning("Jira environment variables not set or library not installed. Jira functionality disabled.")

        confluence_conf = None
        if CONFLUENCE_AVAILABLE and all(k in os.environ for k in ['CONFLUENCE_ENDPOINT', 'CONFLUENCE_API_USER', 'CONFLUENCE_API_TOKEN']):
             try:
                 confluence_conf = ConfluenceConfig(
                     endpoint_url=os.environ['CONFLUENCE_ENDPOINT'],
                     username=os.environ['CONFLUENCE_API_USER'],
                     api_token=os.environ['CONFLUENCE_API_TOKEN']
                 )
             except Exception as e:
                 logger.warning(f"Failed to create ConfluenceConfig: {e}. Confluence functionality disabled.")
        else:
             logger.warning("Confluence environment variables not set or library not installed. Confluence functionality disabled.")

    except (KeyError, ValueError, ImportError, ConnectionError) as e:
        logger.error(f"Failed to load configuration or initialize clients: {e}", exc_info=True)
        print(f"\nFATAL: Could not configure the tool: {e}")
        return

    # --- Instantiate the Tool (This part is unchanged and correct) ---
    try:
        logger.info("Instantiating AdvancedImageAnalyzerTool...")
        advanced_image_analyzer = AdvancedImageAnalyzerTool(
            azure_config=azure_conf,
            jira_config=jira_conf,
            confluence_config=confluence_conf
        )
        logger.info("Tool instantiated.")
    except ToolConfigurationError as e:
         logger.error(f"Failed to instantiate tool: {e}", exc_info=True)
         print(f"\nFATAL: Could not instantiate the tool: {e}")
         return

    # --- CrewAI LLM and Agent Definition (Unchanged and correct) ---
    try:
        agent_llm = LLM(
            model=f"azure/{azure_conf.vision_deployment}",
            api_version=azure_conf.api_version
        )
        logger.info(f"CrewAI LLM Configured using deployment: {azure_conf.vision_deployment}")
    except Exception as e:
        logger.error(f"Error configuring CrewAI LLM for Agent: {e}.", exc_info=True)
        print(f"\nFATAL: Could not configure CrewAI LLM.")
        return

    image_analyzer_agent = Agent(
        role="Multisource Image Analyst",
        goal="Use the Advanced Image Analyzer tool to analyze a mixed list of images from various sources and report the findings for each.",
        backstory="You are an expert AI assistant that meticulously follows instructions to retrieve images from URLs, Jira, or Confluence using self-contained URI formats and analyze their content with a powerful vision model.",
        llm=agent_llm,
        tools=[advanced_image_analyzer],
        verbose=True,
        memory=False,
        allow_delegation=False
    )
    logger.info("Agent defined.")

    # --- AMENDED AND SIMPLIFIED TASK DEFINITION ---
    # We now create a single, powerful task that demonstrates all the tool's capabilities.

    # 1. Dynamically build a list of image references based on available configs.
    all_references = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Test-Logo.svg/1024px-Test-Logo.svg.png",
        # Add an intentionally invalid URL to demonstrate robust error handling
        "https://this-is-a-bad-url-that-will-fail.com/image.png"
    ]

    if jira_conf:
        # !! Replace with your actual Jira details for testing !!
        jira_issue_key = "PROJ-123"
        jira_attachment_filename = "architecture_diagram.png"
        all_references.append(f"jira://{jira_issue_key}/{jira_attachment_filename}")

    if confluence_conf:
        # !! Replace with your actual Confluence details for testing !!
        confluence_page_id = "12345678"
        confluence_attachment_filename = "meeting_whiteboard.jpg"
        all_references.append(f"confluence://{confluence_page_id}/{confluence_attachment_filename}")
    
    # Add an invalid URI format to show another type of error handling
    all_references.append("invalid-scheme://some/file")

    # 2. Join the list into a single newline-separated string for the tool.
    image_references_string = "\n".join(all_references)
    analysis_prompt_string = "Describe the main elements in this image, including any text, colors, and shapes. If it's a diagram, explain its purpose."

    # 3. Create the single, comprehensive task.
    mixed_source_task = Task(
        description=f"""Analyze a list of images from various sources using the 'Advanced Image Analyzer' tool.

        The tool requires two arguments:
        1. 'image_references': A single string with each location on a new line.
        2. 'analysis_prompt': A single string to apply to all images.

        Here are the arguments to use for the tool call:

        image_references:
        {image_references_string}

        analysis_prompt:
        {analysis_prompt_string}
        """,
        expected_output="A structured report containing the analysis for each successfully processed image and a clear error message for each image that failed.",
        agent=image_analyzer_agent
    )

    logger.info(f"Single comprehensive task defined with {len(all_references)} references.")

    # --- Crew Definition and Kickoff ---
    logger.info("Defining and Running Crew with a single, powerful task...")
    analysis_crew = Crew(
        agents=[image_analyzer_agent],
        tasks=[mixed_source_task], # Use our single, powerful task
        process=Process.sequential,
        verbose=True
    )

    try:
        crew_result = analysis_crew.kickoff()
        logger.info("--- Crew Execution Finished ---")
        print("\n\n" + "="*40)
        print("--- FINAL TASK RESULT ---")
        print(crew_result)
        print("="*40 + "\n")

    except Exception as e:
         logger.critical(f"An error occurred during crew kickoff: {e}", exc_info=True)
         print(f"\n--- An error occurred during crew kickoff: {e} ---")

    logger.info("\nScript finished.")


# --- Main Execution Guard ---
if __name__ == "__main__":
    run_crewai_example()