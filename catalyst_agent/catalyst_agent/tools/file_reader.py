# catalyst_agent/catalyst_agent/tools/file_reader.py
import os
from typing import Dict, Any, Optional
from .base import Tool, ToolResult # Use relative import
import logging

logger = logging.getLogger(__name__)

class FileReaderTool(Tool):
    """Reads text content from a specified file. Can read the entire file or a specific line range."""

    def __init__(self, event_queue: Optional[Any] = None):
        super().__init__(
            name="file_reader",
            description="Reads text content from a specified file. Can read the entire file or a specific line range.",
            event_queue=event_queue
        )

    def get_schema(self) -> Dict[str, Any]:
        """Returns the schema for the file_reader tool."""
        return {
            "parameters": {
                "path": {"type": "string", "description": "The relative path to the file to read.", "required": True},
                "start_line": {"type": "integer", "description": "Optional starting line number (1-based).", "required": False},
                "end_line": {"type": "integer", "description": "Optional ending line number (1-based, inclusive).", "required": False}
            },
            "returns": {
                "type": "string",
                "description": "The content read from the file, or an error message."
            }
        }

    def execute(self, **kwargs) -> ToolResult:
        """
        Executes the file reading operation based on the provided inputs.
        """
        file_path = kwargs.get("path")
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        if not file_path:
            return ToolResult.error_result("Missing required parameter: path")

        if not os.path.exists(file_path):
            error_message = f"Error reading file: File not found at {file_path}"
            logger.error(error_message)
            return ToolResult.error_result(error_message)

        if not os.path.isfile(file_path):
             error_message = f"Error reading file: Path {file_path} is a directory, not a file."
             logger.error(error_message)
             return ToolResult.error_result(error_message)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if start_line is not None or end_line is not None:
                    lines = f.readlines()
                    # Adjust to 0-based indexing for slicing
                    start_idx = (start_line - 1) if start_line is not None else 0
                    end_idx = end_line if end_line is not None else len(lines)

                    if start_idx < 0: start_idx = 0
                    if end_idx > len(lines): end_idx = len(lines)
                    if start_idx >= end_idx:
                         content = "" # Return empty if range is invalid
                    else:
                        content = "".join(lines[start_idx:end_idx])

                    line_info = f" (lines {start_line or 1}-{end_idx})" if content else ""
                else:
                    content = f.read()
                    line_info = ""

            success_message = f"Successfully read content from file: {file_path}{line_info}"
            logger.info(success_message)
            # Return the actual content in the result data field
            return ToolResult.success_result(data=content)

        except UnicodeDecodeError as e:
            error_message = f"Error reading file {file_path}: Could not decode file content using UTF-8. It might be a binary file or use a different encoding. {e}"
            logger.error(error_message)
            return ToolResult.error_result(error_message)
        except IOError as e:
            error_message = f"Error reading file {file_path}: {e}"
            logger.error(error_message)
            return ToolResult.error_result(error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred while reading {file_path}: {e}"
            logger.error(error_message, exc_info=True)
            return ToolResult.error_result(error_message)