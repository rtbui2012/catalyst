"""
Web search tool for Agentic Core.

This module provides a tool that allows agents to search the web for information,
enabling access to up-to-date knowledge beyond the agent's training data.
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional
from ..tools import Tool, ToolResult


class WebSearchTool(Tool):
    """
    Tool for performing web searches and retrieving results.
    
    This tool allows the agent to search the web for information,
    enabling it to access up-to-date knowledge.
    """
    
    SUPPORTED_ENGINES = ["google", "bing", "duckduckgo", "serper"]
    
    def __init__(self, 
                 name: str = "web_search", 
                 description: str = "Search the web for information on a topic",
                 api_key: Optional[str] = None,
                 search_engine: str = "bing",
                 cx_id: Optional[str] = None,  # For Google Custom Search
                 max_results: int = 5,
                 include_snippets: bool = True,
                 filter_ads: bool = True):
        """
        Initialize the web search tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
            api_key: API key for the search engine
            search_engine: Search engine to use (google, bing, duckduckgo, serper)
            cx_id: Custom Search Engine ID (required for Google)
            max_results: Maximum number of results to return
            include_snippets: Whether to include text snippets in results
            filter_ads: Whether to filter out advertisements from results
        """
        super().__init__(name, description)
        
        if search_engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported search engine: {search_engine}. "
                           f"Supported engines are: {', '.join(self.SUPPORTED_ENGINES)}")
        
        # For Google, both API key and cx_id are required
        if search_engine == "google" and (not api_key or not cx_id):
            raise ValueError("Both api_key and cx_id are required for Google Custom Search")
            
        # For Bing and Serper, API key is required
        if search_engine in ["bing", "serper"] and not api_key:
            raise ValueError(f"API key is required for {search_engine} search")
        
        self.api_key = api_key
        self.search_engine = search_engine
        self.cx_id = cx_id
        self.max_results = max_results
        self.include_snippets = include_snippets
        self.filter_ads = filter_ads
    
    def execute(self, query: str) -> ToolResult:
        """
        Execute a web search with the provided query.
        
        Args:
            query: The search query
            
        Returns:
            Search results with titles, snippets, and URLs
        """
        try:
            if not query or not isinstance(query, str):
                return ToolResult.error_result("Query must be a non-empty string")
            
            # Execute search based on configured engine
            if self.search_engine == "google":
                results = self._search_google(query)
            elif self.search_engine == "bing":
                results = self._search_bing(query)
            elif self.search_engine == "duckduckgo":
                results = self._search_duckduckgo(query)
            elif self.search_engine == "serper":
                results = self._search_serper(query)
            else:
                return ToolResult.error_result(f"Unsupported search engine: {self.search_engine}")
            
            return ToolResult.success_result(results)
        except Exception as e:
            return ToolResult.error_result(f"Error executing web search: {str(e)}")
    
    def _search_google(self, query: str) -> Dict[str, Any]:
        """
        Perform a Google search using the Custom Search JSON API.
        
        Args:
            query: The search query
            
        Returns:
            Dictionary with search results
        """
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx_id,
            "q": query,
            "num": min(self.max_results, 10)  # Google API limits to 10 per request
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Format the results
        formatted_results = {
            "engine": "Google",
            "query": query,
            "total_results": data.get("searchInformation", {}).get("totalResults", "0"),
            "items": []
        }
        
        for item in data.get("items", []):
            # Skip ads if filter_ads is True
            if self.filter_ads and item.get("displayLink", "").startswith("ad"):
                continue
                
            result_item = {
                "title": item.get("title", ""),
                "link": item.get("link", "")
            }
            
            if self.include_snippets:
                result_item["snippet"] = item.get("snippet", "")
                
            formatted_results["items"].append(result_item)
            
        return formatted_results
    
    def _search_bing(self, query: str) -> Dict[str, Any]:
        """
        Perform a search using the Bing Web Search API.
        
        Args:
            query: The search query
            
        Returns:
            Dictionary with search results
        """
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "q": query,
            "count": self.max_results,
            "responseFilter": "Webpages",
            "textDecorations": False,
            "textFormat": "Raw"
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Format the results
        formatted_results = {
            "engine": "Bing",
            "query": query,
            "total_results": data.get("webPages", {}).get("totalEstimatedMatches", 0),
            "items": []
        }
        
        for item in data.get("webPages", {}).get("value", []):
            result_item = {
                "title": item.get("name", ""),
                "link": item.get("url", "")
            }
            
            if self.include_snippets:
                result_item["snippet"] = item.get("snippet", "")
                
            formatted_results["items"].append(result_item)
            
        return formatted_results
    
    def _search_duckduckgo(self, query: str) -> Dict[str, Any]:
        """
        Perform a search using DuckDuckGo API.
        
        Args:
            query: The search query
            
        Returns:
            Dictionary with search results
        """
        # DuckDuckGo Instant Answer API (free, no auth needed)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Format the results (DuckDuckGo has a different structure)
        formatted_results = {
            "engine": "DuckDuckGo",
            "query": query,
            "items": []
        }
        
        # Include the Abstract result
        if data.get("Abstract"):
            formatted_results["items"].append({
                "title": data.get("Heading", ""),
                "link": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", "")
            })
        
        # Include related topics
        for topic in data.get("RelatedTopics", [])[:self.max_results]:
            if "Topics" in topic:
                # This is a category, skip
                continue
                
            result_item = {
                "title": topic.get("Text", ""),
                "link": topic.get("FirstURL", "")
            }
            
            if self.include_snippets:
                result_item["snippet"] = topic.get("Text", "")
                
            formatted_results["items"].append(result_item)
            
        return formatted_results
    
    def _search_serper(self, query: str) -> Dict[str, Any]:
        """
        Perform a search using Serper.dev API.
        
        Args:
            query: The search query
            
        Returns:
            Dictionary with search results
        """
        url = "https://serpapi.serper.dev/search"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": self.max_results
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Format the results
        formatted_results = {
            "engine": "Serper/Google",
            "query": query,
            "items": []
        }
        
        # Add organic results
        for item in data.get("organic", []):
            result_item = {
                "title": item.get("title", ""),
                "link": item.get("link", "")
            }
            
            if self.include_snippets:
                result_item["snippet"] = item.get("snippet", "")
                
            formatted_results["items"].append(result_item)
            
        return formatted_results
    
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
                    "description": "The search query to execute",
                    "required": True
                }
            },
            "returns": {
                "type": "object",
                "description": "Search results with titles, snippets, and URLs"
            },
            "example": 'web_search(query="latest developments in AI research")'
        }