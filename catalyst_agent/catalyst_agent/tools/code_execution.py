"""
Code execution tool for Agentic Core.

This module provides a tool that allows agents to execute Python code
in a controlled environment.
"""

import os
import sys
import traceback
from typing import Dict, List, Any, Optional, Union
import uuid
import tempfile
import subprocess
import json
import io
import contextlib
from .base import Tool, ToolResult
import logging
from catalyst_agent.event_queue import EventQueue


class DynamicCodeExecutionTool(Tool):
    """
    Tool for dynamically executing Python code.
    
    This tool allows the agent to write and execute Python code on the fly,
    enabling it to solve complex problems programmatically.
    """
    
    def __init__(self, 
                 name: str = "execute_python", 
                 description: str = "Execute Python code dynamically and return the results. Your code "
                  "should output results to stdout. If your code writes a file (e.g., an image, a document) to the "
                  "'./blob_storage' directory, print the relative path (e.g., './blob_storage/my_image.png') to stdout. ",
                 max_execution_time: int = 30,
                 allowed_imports: Optional[list] = None,
                 event_queue: Optional[EventQueue] = None):
        """
        Initialize the dynamic code execution tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
            max_execution_time: Maximum execution time in seconds (not implemented yet)
            allowed_imports: List of allowed import modules, if None all imports are allowed
            event_queue: Optional event queue for tool events
        """
        super().__init__(name, description, event_queue=event_queue)
        self.max_execution_time = max_execution_time
        self.allowed_imports = allowed_imports
        # Initialize logger for the tool instance
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def execute(self, code: str, variables: Optional[Dict[str, Any]] = None) -> ToolResult:
        """
        Execute the provided Python code and return the results.
        
        Args:
            code: The Python code to execute
            variables: Optional dictionary of variables to inject into the execution context
            
        Returns:
            Result of the code execution with stdout, stderr, and return value
        """
        if not code or not isinstance(code, str):
            return ToolResult.error_result("Code must be a non-empty string")
        
        # Removed temporary file creation - will execute code string directly
        # Create string buffers for capturing stdout/stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        # Prepare execution context with injected variables
        exec_locals = {}
        if variables and isinstance(variables, dict):
            exec_locals.update(variables)
        
        # Variable to store the return value if any
        return_value = None
        
        try:
            # Check if code has a return statement at the end
            has_return = False
            code_lines = code.strip().split('\n')
            if code_lines and code_lines[-1].startswith('return '):
                has_return = True
                # Replace return with a variable assignment
                code_lines[-1] = f"__return_value__ = {code_lines[-1][7:]}"
                code = '\n'.join(code_lines)
            
            # Execute the code and capture stdout/stderr
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                # Execute the code string directly
                compiled_code = compile(code, '<string>', 'exec')
                exec(compiled_code, globals(), exec_locals)
                
                # Get the return value if there was one
                if has_return:
                    return_value = exec_locals.get('__return_value__')
            
            # Prepare the result
            stdout = stdout_buffer.getvalue()
            stderr = stderr_buffer.getvalue()
            
            result_data = {
                "stdout": stdout,
                "stderr": stderr,
                "return_value": return_value
            }

            print(f"Code execution std result: {result_data}")
            
            # Check stderr and stdout for actual error patterns
            execution_error = None
            error_keywords = ["error", "exception", "traceback", "failed"] # Case-insensitive check below

            if stderr:
                stderr_lower = stderr.lower()
                # Check if stderr contains actual error keywords
                if any(keyword in stderr_lower for keyword in error_keywords):
                    execution_error = f"Code execution produced error messages on stderr:\n{stderr}"
                else:
                    # Log non-error stderr content as warning but don't fail automatically
                    self.logger.warning(f"Code execution produced non-error output on stderr (e.g., progress bar):\n{stderr}")

            # Check stdout for "Error:" only if no critical error found in stderr yet
            if not execution_error and "error:" in stdout.lower():
                 self.logger.debug("Found 'Error:' pattern in stdout.")
                 execution_error = f"Code execution produced potential error messages on stdout:\n{stdout}"

            if execution_error:
                self.logger.warning(f"Code execution flagged as failed due to detected errors: {execution_error}")
                # Return failure result only if specific error patterns were detected
                return ToolResult(success=False, data=result_data, error=execution_error)
            else:
                # No apparent errors in output, return success
                self.logger.info(f"Code execution successful. stdout: {stdout[:100]}..., stderr: {stderr[:100]}...")
                return ToolResult.success_result(result_data)
            
        except Exception as e:
            # Get the traceback information
            tb = traceback.format_exc()
            
            # Include any output up to the error
            stdout = stdout_buffer.getvalue()
            stderr = stderr_buffer.getvalue()
            
            error_message = f"Error executing code: {str(e)}\n{tb}"
            
            # Create a new ToolResult directly instead of using error_result
            # This avoids the issue with the error_result method expecting only one argument
            return ToolResult(
                success=False, 
                data={
                    "stdout": stdout,
                    "stderr": stderr + "\n" + tb,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }, 
                error=error_message
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.
        
        Returns:
            Dictionary representing the tool's parameter schema
        """
        return {
            "parameters": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute",
                    "required": True
                },
                "variables": {
                    "type": "object",
                    "description": "Optional dictionary of variables to inject into the execution context",
                    "required": False
                }
            },
            "returns": {
                "type": "object",
                "description": "Result of the code execution with stdout, stderr, and return value"
            },
            "example": 'execute_python(code="import datetime\\nprint(f\\"Current date and time: {datetime.datetime.now()}\\")")'
        }