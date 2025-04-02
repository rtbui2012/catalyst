"""
Core tool abstractions for the Agentic Core.

This module provides the base classes for creating and managing tools
that extend the agent's capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
import inspect
import uuid
from catalyst_agent.event_queue import EventQueue

class ToolResult:
    """Result of a tool execution."""
    
    def __init__(self, success: bool, data: Any = None, 
                 error: Optional[str] = None):
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
    
    def __init__(self, name: str, description: str, event_queue: Optional[EventQueue] = None):
        """
        Initialize a tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.event_queue = event_queue or EventQueue()
    
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
    Registry for tools available to the agent.
    
    This class manages the registration and lookup of tools, as well as
    maintaining metadata about tool capabilities and error handling strategies.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools = {}
        self._error_handlers = {}  # Map of error patterns to tool names that can handle them
    
    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool with the registry.
        
        Args:
            tool: The tool to register
        """
        self._tools[tool.name] = tool
        
        # If the tool has declared error handling capabilities, register those
        if hasattr(tool, 'get_error_handlers') and callable(getattr(tool, 'get_error_handlers')):
            error_handlers = tool.get_error_handlers()
            for error_pattern, handler_info in error_handlers.items():
                self._error_handlers[error_pattern] = handler_info
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Name of the tool to get
            
        Returns:
            The tool if found, None otherwise
        """
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        """
        Get all registered tools.
        
        Returns:
            List of all registered tools
        """
        return list(self._tools.values())
    
    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name with the given arguments.
        
        Args:
            name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult.error_result(f"Tool '{name}' not found")
        
        # Check if tool has pre-execution capabilities
        if hasattr(tool, 'pre_execute') and callable(getattr(tool, 'pre_execute')):
            modified_kwargs = tool.pre_execute(**kwargs)
            if modified_kwargs is not None:
                kwargs = modified_kwargs
        
        tool.event_queue.add_tool_input(
            tool_name=tool.name,
            tool_args=kwargs,
            metadata={"tool_name": tool.name}
        )

        # Execute the tool
        result = tool.execute(**kwargs)

        tool.event_queue.add_tool_output(
            tool_name=tool.name,
            success=result.success,
            data=result.data,
            error=result.error,
            metadata={"tool_name": tool.name}
        )
        
        # Check if tool has post-execution capabilities
        if hasattr(tool, 'post_execute') and callable(getattr(tool, 'post_execute')):
            modified_result = tool.post_execute(result, **kwargs)
            if modified_result is not None:
                result = modified_result
        
        return result
    
    def find_error_handler(self, error_message: str) -> Optional[Dict[str, Any]]:
        """
        Find a tool that can handle a specific error pattern.
        
        Args:
            error_message: The error message to find a handler for
            
        Returns:
            Information about the error handler if found, None otherwise
        """
        if not error_message:
            return None
            
        for pattern, handler_info in self._error_handlers.items():
            if pattern in error_message:
                return handler_info
                
        return None
    
    def create_recovery_step(self, error_message: str, failed_step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a recovery step for a failed step based on registered error handlers.
        
        Args:
            error_message: The error message from the failed step
            failed_step: Information about the failed step
            
        Returns:
            A recovery step if an appropriate handler is found, None otherwise
        """
        handler = self.find_error_handler(error_message)
        if not handler:
            return None
            
        recovery_tool = handler.get('tool')
        arg_generator = handler.get('arg_generator')
        
        if not recovery_tool or not arg_generator:
            return None
            
        # Generate arguments for the recovery step
        recovery_args = arg_generator(error_message, failed_step)
        
        # Create the recovery step
        return {
            'description': handler.get('description', f"Recover from error using {recovery_tool}"),
            'tool_name': recovery_tool,
            'tool_args': recovery_args
        }