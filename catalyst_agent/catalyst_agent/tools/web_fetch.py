"""
Web fetching tool for Agentic Core.

This module provides a tool that allows agents to fetch and extract content
from web pages.
"""

import requests
from typing import Dict, Any
from bs4 import BeautifulSoup
from .base import Tool, ToolResult
from html2text import HTML2Text
from urllib.parse import urlparse


class WebFetchTool(Tool):
    """
    Tool for fetching and extracting text content from web pages.
    
    This tool allows the agent to retrieve text content from specific URLs,
    enabling it to follow links from search results and extract
    the actual text content from web pages. Note that this tool ignores 
    images and only processes textual content (HTML converted to markdown).
    """
    
    def __init__(self, 
                 name: str = "web_fetch_text_only", 
                 description: str = "Fetch text content from a web page URL. Do not use this tool to fetch binary content like images. ",
                 max_content_length: int = 10000,
                 user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"):
        """
        Initialize the web fetch tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
            max_content_length: Maximum length of content to return (in characters)
            user_agent: User agent string to use for requests
        """
        super().__init__(name, description)
        self.max_content_length = max_content_length
        self.user_agent = user_agent
        self.html_converter = HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_tables = False
        self.html_converter.body_width = 0  # No wrapping

    def execute(self, url: str, extract_type: str = "full") -> ToolResult:
        """
        Execute the web fetch operation.
        
        Args:
            url: The URL to fetch content from
            extract_type: The type of content to extract (full, main, summary)
            
        Returns:
            Extracted web content
        """
        try:
            if not url or not isinstance(url, str):
                return ToolResult.error_result("URL must be a non-empty string")
            
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return ToolResult.error_result(f"Invalid URL: {url}")
                
            # Fetch the web page
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise exception for 4XX/5XX status codes
            
            # Check content type to ensure we're only processing HTML/text content
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return ToolResult.error_result(
                    f"This tool only processes HTML or text content. Received content type: {content_type}. "
                    f"Binary content like images cannot be processed by this tool."
                )
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove unwanted elements (ads, navigation, etc.)
            for element in soup.select("script, style, nav, footer, .ad, .advertisement, .nav, .menu, .sidebar"):
                element.decompose()
            
            result_data = {}
            result_data["url"] = url
            result_data["title"] = soup.title.text.strip() if soup.title else ""
            
            # Extract content based on the requested type
            if extract_type == "main":
                # Try to extract main content by finding the largest text block
                main_content = self._extract_main_content(soup)
                content = self.html_converter.handle(str(main_content))
            elif extract_type == "summary":
                # Extract a summary of the content
                content = self._extract_summary(soup)
            else:  # "full" content
                # Convert the entire cleaned HTML to text
                content = self.html_converter.handle(str(soup))
            
            # Truncate content if it's too long
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n[Content truncated...]"
            
            result_data["content"] = content
            result_data["content_type"] = extract_type
            result_data["length"] = len(content)
            
            return ToolResult.success_result(result_data)
        except requests.exceptions.RequestException as e:
            return ToolResult.error_result(f"Error fetching URL: {str(e)}")
        except Exception as e:
            return ToolResult.error_result(f"Error processing web content: {str(e)}")

    def _extract_main_content(self, soup):
        """Extract the main content of a web page."""
        # Look for common content containers
        for container in ["main", "article", "#content", ".content", ".post", ".article", "#main"]:
            main_element = soup.select_one(container)
            if main_element and len(main_element.get_text(strip=True)) > 200:
                return main_element
        
        # If no common container found, find the element with the most text
        paragraphs = soup.find_all('p')
        if paragraphs:
            # Find the div that contains the most paragraphs
            div_paragraph_counts = {}
            for p in paragraphs:
                parents = list(p.parents)
                for parent in parents:
                    if parent.name == 'div':
                        div_paragraph_counts[parent] = div_paragraph_counts.get(parent, 0) + 1
            
            if div_paragraph_counts:
                main_div = max(div_paragraph_counts.items(), key=lambda x: x[1])[0]
                return main_div
        
        # Fall back to body if no better container found
        return soup.body or soup

    def _extract_summary(self, soup):
        """Extract a summary of the web page content."""
        # Try to find meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        summary = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else ""
        
        # If no meta description or it's too short, extract first few paragraphs
        if len(summary) < 100:
            paragraphs = soup.find_all('p')
            content = "\n\n".join([p.get_text(strip=True) for p in paragraphs[:5]])
            summary = content[:500] + "..." if len(content) > 500 else content
        
        return summary

    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.
        
        Returns:
            Dictionary representing the tool's parameter schema
        """
        return {
            "parameters": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                    "required": True
                },
                "extract_type": {
                    "type": "string",
                    "description": "The type of content to extract: 'full' (entire page), 'main' (main content), or 'summary' (brief summary)",
                    "enum": ["full", "main", "summary"],
                    "required": False,
                    "default": "full"
                }
            },
            "returns": {
                "type": "object",
                "description": "Web page content with metadata"
            },
            "example": 'web_fetch(url="https://example.com", extract_type="main")'
        }

