"""
Image Search tool for Agentic Core.

This module provides a tool that allows agents to search for images using Google Custom Search API.
"""

import os
import requests
from typing import Dict, List, Any, Optional
from .base import Tool, ToolResult
from catalyst_agent.event_queue import EventQueue

class ImageSearchTool(Tool):
    """
    Tool for performing image searches using Google Custom Search API and retrieving results.

    This tool allows the agent to search for images for visual information.
    Requires Google API Key and Custom Search Engine ID configured for image search.
    """

    def __init__(self,
                 name: str = "image_search",
                 description: str = "Search for images related to a query.",
                 api_key: Optional[str] = None,
                 cx_id: Optional[str] = None,
                 max_results: int = 10, # Google API typically returns 10 images max per request
                 event_queue: Optional[EventQueue] = None):
        """
        Initialize the Image search tool.

        Args:
            name: Name of the tool
            description: Description of what the tool does
            api_key: Google API key (if None, will try to load from GOOGLE_API_KEY environment variable)
            cx_id: Google Custom Search Engine ID (if None, will try to load from GOOGLE_CX_ID environment variable)
            max_results: Maximum number of image results to return (limited by API)
            event_queue: Optional event queue for logging/events
        """
        super().__init__(name, description, event_queue=event_queue)

        # Set API key using env var as fallback
        if api_key is None:
            api_key = os.environ.get("GOOGLE_API_KEY")

        # Set CX ID using env var as fallback
        if cx_id is None:
            cx_id = os.environ.get("GOOGLE_CX_ID")

        # Both API key and cx_id are required
        if not api_key or not cx_id:
            raise ValueError("Both api_key and cx_id are required for Google Custom Search. "
                           "Set them directly or via GOOGLE_API_KEY and GOOGLE_CX_ID environment variables.")

        self.api_key = api_key
        self.cx_id = cx_id
        self.max_results = min(max_results, 10) # Enforce API limit

    def execute(self, query: str, max_results: Optional[int] = None) -> ToolResult:
        """
        Execute an image search with the provided query.

        Args:
            query: The search query
            max_results: Optional maximum number of results to return (1-10). Defaults to the value set during initialization (or 10).

        Returns:
            A Markdown string for the first image found (e.g., ![alt text](url)), or a message indicating no results.
        """
        try:
            if not query or not isinstance(query, str):
                return ToolResult.error_result("Query must be a non-empty string")

            # Determine the number of results to request
            num_to_request = self.max_results # Start with the default/init value
            if max_results is not None:
                if isinstance(max_results, int) and 1 <= max_results <= 10:
                    num_to_request = max_results
                else:
                    # Optionally log a warning or inform the user about invalid input?
                    # For now, just clamp or use default. Let's clamp to the valid range.
                    num_to_request = max(1, min(max_results, 10)) if isinstance(max_results, int) else self.max_results


            results = self._search_images(query, num_results=num_to_request)
            # Check if results is a string (Markdown or error message)
            if isinstance(results, str):
                 return ToolResult.success_result(results)
            else:
                 # Should not happen based on _search_images logic, but handle defensively
                 return ToolResult.error_result("Unexpected result format from image search.")
        except requests.exceptions.RequestException as req_err:
             return ToolResult.error_result(f"API request failed: {str(req_err)}")
        except Exception as e:
            return ToolResult.error_result(f"Error executing image search: {str(e)}")

    def _search_images(self, query: str, num_results: int) -> str:
        """
        Perform an image search using the Google Custom Search JSON API and return the first result as Markdown.

        Args:
            query: The search query
            num_results: The number of results to request from the API (1-10)

        Returns:
            A Markdown image tag string for the first result, or a 'No image found' message.
        """
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx_id,
            "q": query,
            "searchType": "image", # Specify image search
            "num": num_results
        }

        response = requests.get(url, params=params)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        # Process the results to get the first image as Markdown
        items = data.get("items", [])
        if items:
            first_item = items[0]
            title = first_item.get("title", query) # Use query as fallback alt text
            image_url = first_item.get("link", "")

            if image_url:
                # Escape potential Markdown characters in title (like brackets)
                safe_title = title.replace("[", "\\[").replace("]", "\\]")
                return f"![{safe_title}]({image_url})"
            else:
                return f"Found an image result for '{query}' but it missing a URL."
        else:
            return f"No image found for '{query}'."

    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.

        Returns:
            Dictionary representing the tool's parameter schema
        """
        return {
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "The image search query to execute",
                    "required": True
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of image results to return (1-10). Defaults to 10 or the value set at initialization.",
                    "required": False
                }
            },
            "returns": {
                "type": "string",
                "description": "A Markdown image tag for the first result found (e.g., ![alt text](url)), or a message indicating no results were found."
            },
            "example": 'image_search(query="pictures of cats", max_results=1) -> ![Cute cat](https://example.com/cat.jpg)'
        }