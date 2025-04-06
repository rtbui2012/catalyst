"""
Tool management interfaces for the Agentic Core.

This module provides abstractions for discovering, registering, and using
tools that extend the agent's capabilities.
"""

# Import core classes from base module
from .base import Tool, ToolResult, FunctionTool, ToolRegistry

# Import specialized tools
from .code_execution import DynamicCodeExecutionTool
from .image_generation import ImageGenerationTool
from .web_search import WebSearchTool
from .web_fetch import WebFetchTool
from .package_manager import PackageInstallerTool
from .download_file import DownloadFileTool
from .image_search import ImageSearchTool
from .file_writer import FileWriterTool
from .file_reader import FileReaderTool
# Import discovery utilities
from .discovery import discover_tools, instantiate_tool

__all__ = [
    'Tool', 
    'ToolResult', 
    'FunctionTool', 
    'ToolRegistry', 
    'DynamicCodeExecutionTool',
    'ImageGenerationTool',
    'WebSearchTool',
    'WebFetchTool',
    'PackageInstallerTool',
    'DownloadFileTool',
    'ImageSearchTool',
    'FileWriterTool',
    'FileReaderTool',
    'discover_tools',
    'instantiate_tool'
]