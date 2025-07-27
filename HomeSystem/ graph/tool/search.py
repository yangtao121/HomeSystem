
"""Search tool implementations for different search engines."""

import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_community.utilities import SearxSearchWrapper
from langchain_community.tools.searx_search.tool import SearxSearchResults
from langchain_community.tools.tavily_search import TavilySearchResults


class BaseSearchTool(ABC):
    """Abstract base class for search tools."""
    
    @abstractmethod
    def get_search_tool(self):
        """Get the search tool instance.
        
        Returns:
            The configured search tool instance.
        """
        pass

class SearxSearchTool(BaseSearchTool):
    """Search tool implementation using SearX search engine."""
    
    def __init__(self, searx_host: str, max_results: int = 10, search_engines: list = ["arxiv", "bing"]):
        """Initialize SearX search tool.
        
        Args:
            searx_host: The SearX host URL
            max_results: Maximum number of search results to return
        """
        if not searx_host:
            raise ValueError("searx_host cannot be empty")
            
        try:
            search_wrapper = SearxSearchWrapper(searx_host=searx_host)
            self.search_tool = SearxSearchResults(
                wrapper=search_wrapper,
                kwargs={
                    "engines": ["ask", "360search", "alexandria", "wikisource", "bing", "baidu"],
                    "max_results": max_results,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize SearX search tool: {e}")

    def get_search_tool(self):
        """Get the SearX search tool instance."""
        return self.search_tool


class TavilySearchTool(BaseSearchTool):
    """Search tool implementation using Tavily search engine."""
    
    def __init__(self, tavily_api_key: str, max_results: int = 5):
        """Initialize Tavily search tool.
        
        Args:
            tavily_api_key: The Tavily API key
            max_results: Maximum number of search results to return
        """
        if not tavily_api_key:
            raise ValueError("tavily_api_key cannot be empty")
            
        try:
            os.environ["TAVILY_API_KEY"] = tavily_api_key
            self.search_tool = TavilySearchResults(max_results=max_results)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Tavily search tool: {e}")
        
    def get_search_tool(self):
        """Get the Tavily search tool instance."""
        return self.search_tool