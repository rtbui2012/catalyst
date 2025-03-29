"""
Core tool abstractions for the Agentic Core.

This module provides the base classes for creating and managing tools
that extend the agent's capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Type, TypeVar, Generic, Union
import json
import inspect
import uuid


class ToolResult:
    """Result of a tool execution."""
    
    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        """
        Initialize a tool result.
        
        Args:
            success: Whether the tool execution was successful
            data: Result data if successful
            error: Error message if unsuccessful
        """
        self.success = success
        self.data = data
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool result to a dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }
    
    @classmethod
    def success_result(cls, data: Any = None) -> 'ToolResult':
        """Create a successful tool result."""
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str) -> 'ToolResult':
        """Create an error tool result."""
        return cls(success=False, error=error)
    
    def __bool__(self) -> bool:
        """Boolean representation of the tool result (True if successful)."""
        return self.success


class Tool(ABC):
    """Abstract base class for tools that extend the agent's capabilities."""
    
    def __init__(self, name: str, description: str):
        """
        Initialize a tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with the provided arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            Result of the tool execution
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.
        
        Returns:
            Dictionary representing the tool's parameter schema
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "schema": self.get_schema()
        }
    
    def __str__(self) -> str:
        """String representation of the tool."""
        return f"{self.name}: {self.description}"


class FunctionTool(Tool):
    """A tool that wraps a Python function."""
    
    def __init__(
        self, 
        func: Callable, 
        name: Optional[str] = None, 
        description: Optional[str] = None
    ):
        """
        Initialize a function tool.
        
        Args:
            func: The function to wrap
            name: Name of the tool (defaults to function name)
            description: Description of what the tool does (defaults to function docstring)
        """
        self.func = func
        
        # Get name and description from function if not provided
        name = name or func.__name__
        description = description or (func.__doc__ or f"Execute {name} function")
        
        super().__init__(name, description)
        
        # Get function signature for parameter schema
        self.signature = inspect.signature(func)
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute the wrapped function with the provided arguments."""
        try:
            # Check if all required parameters are provided
            for param_name, param in self.signature.parameters.items():
                if param.default == inspect.Parameter.empty and param_name not in kwargs:
                    return ToolResult.error_result(f"Missing required parameter: {param_name}")
            
            # Execute the function
            result = self.func(**kwargs)
            return ToolResult.success_result(result)
        except Exception as e:
            return ToolResult.error_result(f"Error executing {self.name}: {str(e)}")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get a schema describing the function's parameters."""
        parameters = {}
        
        for param_name, param in self.signature.parameters.items():
            param_info = {
                "type": "any",
                "description": f"Parameter {param_name}"
            }
            
            # Check if parameter has a type annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == str:
                    param_info["type"] = "string"
                elif param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_info["type"] = "array"
                elif param.annotation == dict or param.annotation == Dict:
                    param_info["type"] = "object"
            
            # Check if parameter has a default value
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
                param_info["required"] = False
            else:
                param_info["required"] = True
            
            parameters[param_name] = param_info
        
        return {
            "parameters": parameters,
            "returns": {
                "type": "any",
                "description": "Result of the function execution"
            }
        }


class ToolRegistry:
    """
    Registry for managing available tools.
    
    This class provides functionality for registering tools, discovering
    available tools, and selecting the appropriate tool for a task.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools: Dict[str, Tool] = {}  # Map of tool name to tool
    
    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: The tool to register
        """
        self.tools[tool.name] = tool
    
    def register_function(
        self, 
        func: Callable, 
        name: Optional[str] = None, 
        description: Optional[str] = None
    ) -> None:
        """
        Register a function as a tool.
        
        Args:
            func: The function to register
            name: Name for the tool (defaults to function name)
            description: Description of what the tool does (defaults to function docstring)
        """
        tool = FunctionTool(func, name, description)
        self.register_tool(tool)
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a specific tool by name.
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            The tool if found, None otherwise
        """
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> List[Tool]:
        """
        Get all registered tools.
        
        Returns:
            List of all registered tools
        """
        return list(self.tools.values())
    
    def search_tools(self, query: str) -> List[Tool]:
        """
        Search for tools matching a query.
        
        Args:
            query: Search query (matches against tool name and description)
            
        Returns:
            List of tools matching the query
        """
        query = query.lower()
        return [
            tool for tool in self.tools.values()
            if query in tool.name.lower() or query in tool.description.lower()
        ]
    
    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name with the provided arguments.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult.error_result(f"Tool not found: {tool_name}")
        
        return tool.execute(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool registry to a dictionary."""
        return {
            "tools": {name: tool.to_dict() for name, tool in self.tools.items()}
        }