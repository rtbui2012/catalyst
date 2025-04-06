# catalyst_agent/catalyst_agent/tools/file_writer.py
import os
from typing import Dict, Any, Optional
from .base import Tool, ToolResult # Use relative import
import logging

logger = logging.getLogger(__name__)

class FileWriterTool(Tool):
    """Writes text content to a specified file, either overwriting or appending."""

    def __init__(self, event_queue: Optional[Any] = None):
        super().__init__(
            name="file_writer",
            description="Writes text content to a specified file, either overwriting existing content or appending to it.",
            event_queue=event_queue
        )

    def get_schema(self) -> Dict[str, Any]:
        """Returns the schema for the file_writer tool."""
        return {
            "parameters": {
                "path": {"type": "string", "description": "The relative path to the file to write.", "required": True},
                "content": {"type": "string", "description": "The content to write to the file.", "required": True},
                "mode": {"type": "string", "description": "Write mode: 'overwrite' or 'append'. Defaults to 'overwrite'.", "required": False, "default": "overwrite"}
            },
            "returns": {
                "type": "string",
                "description": "A message indicating success or failure."
            }
        }

    def execute(self, **kwargs) -> ToolResult:
        """
        Executes the file writing operation based on the provided inputs.
        """
        file_path = kwargs.get("path")
        content = kwargs.get("content")
        mode = kwargs.get("mode", "overwrite").lower() # Default to overwrite

        if not file_path:
            return ToolResult.error_result("Missing required parameter: path")
        if content is None: # Allow empty string content, but not missing content
             return ToolResult.error_result("Missing required parameter: content")

        if mode not in ["overwrite", "append"]:
            return ToolResult.error_result(f"Invalid mode '{kwargs.get('mode')}'. Must be 'overwrite' or 'append'.")

        file_mode = 'w' if mode == "overwrite" else 'a'

        try:
            # Ensure the directory exists
            dir_path = os.path.dirname(file_path)
            if dir_path: # Check if dir_path is not empty (i.e., not writing to root)
                os.makedirs(dir_path, exist_ok=True)

            with open(file_path, file_mode, encoding='utf-8') as f:
                f.write(content)

            action = "overwritten" if mode == "overwrite" else "appended to"
            success_message = f"Successfully {action} file: {file_path}"
            logger.info(success_message)
            return ToolResult.success_result(success_message)

        except IOError as e:
            error_message = f"Error writing to file {file_path}: {e}"
            logger.error(error_message)
            return ToolResult.error_result(error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred while writing to {file_path}: {e}"
            logger.error(error_message, exc_info=True)
            return ToolResult.error_result(error_message)