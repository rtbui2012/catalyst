"""
File downloading tool for Catalyst Agent.

This module provides a tool that allows agents to download content from a URL
directly to the local filesystem.
"""

import requests
import os
import re
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse, unquote
from .base import Tool, ToolResult
from catalyst_agent.event_queue import EventQueue

# Helper function to sanitize filenames
def sanitize_filename(filename: str) -> str:
    """Remove potentially unsafe characters from a filename."""
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    # Limit length to avoid issues with filesystem limits
    return sanitized[:200]

# Helper function to get filename from Content-Disposition header
def get_filename_from_headers(headers: Dict[str, str]) -> Optional[str]:
    """Extract filename from Content-Disposition header."""
    content_disposition = headers.get('Content-Disposition')
    if content_disposition:
        # Regex to find filename*=UTF-8'' or filename="filename.ext"
        match_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
        if match_utf8:
            filename = unquote(match_utf8.group(1))
            return sanitize_filename(filename)

        match_ascii = re.search(r'filename="([^"]+)"', content_disposition, re.IGNORECASE)
        if match_ascii:
            filename = match_ascii.group(1)
            return sanitize_filename(filename)
    return None

# Helper function to get filename from URL path
def get_filename_from_url(url: str) -> Optional[str]:
    """Extract filename from the URL path."""
    try:
        parsed_url = urlparse(url)
        path = unquote(parsed_url.path)
        if path and path != '/':
            filename = path.split('/')[-1]
            if filename: # Ensure it's not empty if URL ends with /
                return sanitize_filename(filename)
    except Exception:
        pass # Ignore parsing errors
    return None

class DownloadFileTool(Tool):
    """
    Tool for downloading content from a URL to a local file.

    This tool fetches content from a given URL and saves it directly to the
    local filesystem, returning metadata about the downloaded file, including
    its path relative to the workspace root. It's suitable for handling
    various content types (binary, text, large files) without loading them
    into memory or the LLM context.
    """

    def __init__(self,
                 name: str = "download_file",
                 description: str = "Download content from a URL and save it to a local file. Returns the file path and metadata.",
                 default_output_dir: str = "data/downloads",
                 event_queue: Optional[EventQueue] = None):
        """
        Initialize the download file tool.

        Args:
            name: Name of the tool.
            description: Description of what the tool does.
            default_output_dir: Default directory to save downloaded files (relative to workspace root).
            event_queue: Optional event queue for logging/events.
        """
        super().__init__(name, description, event_queue=event_queue)
        # Store the relative default path
        self.default_output_dir_rel = default_output_dir
        # Assume workspace root is the current working directory when the tool is initialized
        # In a real scenario, this might need to be passed in or determined differently.
        self.workspace_root = Path.cwd() # Or get from config

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the workspace root."""
        return (self.workspace_root / relative_path).resolve()

    def _get_unique_filename(self, dir_path: Path, filename: str) -> Path:
        """Generate a unique filename if the target file already exists."""
        filepath = dir_path / filename
        if not filepath.exists():
            return filepath

        # File exists, generate a unique name
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_filename = f"{base}_{counter}{ext}"
            new_filepath = dir_path / new_filename
            if not new_filepath.exists():
                return new_filepath
            counter += 1
            if counter > 1000: # Safety break
                 # Fallback to UUID if too many conflicts
                 return dir_path / f"{base}_{uuid.uuid4().hex[:8]}{ext}"


    def execute(self, url: str, output_dir: Optional[str] = None, filename: Optional[str] = None) -> ToolResult:
        """
        Execute the file download operation.

        Args:
            url: The URL of the resource to download.
            output_dir: The directory within the workspace to save the file (relative path).
                        Defaults to `data/downloads`.
            filename: A specific name for the saved file. If omitted, the tool
                      will attempt to derive it from headers or URL.

        Returns:
            ToolResult containing metadata about the downloaded file or an error.
        """
        try:
            # 1. Validate URL
            if not url or not isinstance(url, str):
                return ToolResult.error_result("URL must be a non-empty string")
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return ToolResult.error_result(f"Invalid URL scheme or network location: {url}")

            # 2. Determine and ensure output directory exists
            target_dir_rel = output_dir or self.default_output_dir_rel
            target_dir_abs = self._resolve_path(target_dir_rel)

            try:
                target_dir_abs.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return ToolResult.error_result(f"Failed to create output directory '{target_dir_abs}': {e}")

            # 3. Fetch content with streaming
            headers = {"User-Agent": "CatalystAgent/1.0"} # Basic user agent
            response = requests.get(url, headers=headers, stream=True, timeout=30) # 30s timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # 4. Determine filename
            final_filename = None
            if filename: # User-provided filename takes precedence
                final_filename = sanitize_filename(filename)
            else:
                final_filename = get_filename_from_headers(response.headers)
                if not final_filename:
                    final_filename = get_filename_from_url(url)
                if not final_filename:
                    # Fallback if no name could be derived
                    content_type = response.headers.get('Content-Type', 'application/octet-stream').split(';')[0]
                    ext = f".{content_type.split('/')[-1]}" if '/' in content_type else ".bin"
                    final_filename = f"download_{uuid.uuid4().hex[:8]}{ext}"

            # 5. Handle conflicts and get final path
            target_filepath_abs = self._get_unique_filename(target_dir_abs, final_filename)
            target_filepath_rel = target_filepath_abs.relative_to(self.workspace_root)

            # 6. Stream response to file
            file_size = 0
            chunk_size = 8192 # 8KB chunks
            with open(target_filepath_abs, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        file_size += len(chunk)

            # 7. Gather metadata
            content_type = response.headers.get('Content-Type', 'unknown')

            result_data = {
                "local_path": str(target_filepath_rel),
                "original_url": url,
                "content_type": content_type,
                "file_size": file_size,
                "status": "Download successful"
            }
            return ToolResult.success_result(result_data)

        except requests.exceptions.Timeout:
            return ToolResult.error_result(f"Timeout error fetching URL: {url}")
        except requests.exceptions.RequestException as e:
            return ToolResult.error_result(f"Network error fetching URL '{url}': {e}")
        except OSError as e:
            return ToolResult.error_result(f"File system error: {e}")
        except Exception as e:
            # Catch unexpected errors
            return ToolResult.error_result(f"An unexpected error occurred: {e}")

    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.

        Returns:
            Dictionary representing the tool's parameter schema.
        """
        return {
            "parameters": {
                "url": {
                    "type": "string",
                    "description": "The URL of the resource to download.",
                    "required": True
                },
                "output_dir": {
                    "type": "string",
                    "description": f"Optional directory within the workspace to save the file (relative path). Defaults to '{self.default_output_dir_rel}'.",
                    "required": False
                },
                "filename": {
                    "type": "string",
                    "description": "Optional specific name for the saved file. If omitted, the tool will derive it from headers or URL.",
                    "required": False
                }
            },
            "returns": {
                "type": "object",
                "description": "Metadata about the downloaded file.",
                "properties": {
                    "local_path": {"type": "string", "description": "Relative path to the downloaded file within the workspace."},
                    "original_url": {"type": "string", "description": "The URL the file was downloaded from."},
                    "content_type": {"type": "string", "description": "The Content-Type reported by the server."},
                    "file_size": {"type": "integer", "description": "Size of the downloaded file in bytes."},
                    "status": {"type": "string", "description": "Status message ('Download successful' or error details)."}
                }
            },
            "example": 'download_file(url="https://example.com/data.csv", output_dir="data/project_files", filename="dataset.csv")'
        }