"""
Image generation tool for Agentic Core.

This module provides a tool that allows agents to generate images using 
various image generation services.
"""

import os
import base64
import requests
from typing import Dict, List, Any, Optional, Union
from .base import Tool, ToolResult
from catalyst_agent.event_queue import EventQueue

class ImageGenerationTool(Tool):
    """
    Tool for generating images using Azure OpenAI DALL-E 3.
    
    This tool allows the agent to create images based on text prompts,
    enabling visual content generation capabilities.
    """
    
    SUPPORTED_MODELS = ["dall-e-3"]
    SUPPORTED_SIZES = ["1024x1024", "1792x1024", "1024x1792"]
    SUPPORTED_QUALITIES = ["standard", "hd"]
    
    def __init__(self, 
                 name: str = "generate_image", 
                 description: str = "Generate an image based on a text description using DALL-E 3",
                 api_key: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 model: str = "dall-e-3",
                 size: str = "1024x1024",
                 quality: str = "standard",
                 response_format: str = "url",
                 save_directory: Optional[str] = None,
                 event_queue: Optional[EventQueue] = None):
        """
        Initialize the image generation tool.
        
        Args:
            name: Name of the tool
            description: Description of what the tool does
            api_key: Azure OpenAI API key (can be set via AZURE_OPENAI_DALLE_KEY env variable)
            endpoint: Azure OpenAI endpoint (can be set via AZURE_OPENAI_DALLE_ENDPOINT env variable)
            model: DALL-E model to use (default: "dall-e-3")
            size: Image size (default: "1024x1024")
            quality: Image quality (default: "standard")
            response_format: Response format (url or b64_json)
            save_directory: Directory to save images (if None, images are not saved)
        """
        super().__init__(name, description, event_queue=event_queue)
        
        # Get API key and endpoint from environment variables if not provided
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_DALLE_KEY")
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_DALLE_ENDPOINT")
        
        if not self.api_key:
            raise ValueError("API key is required. Provide via 'api_key' parameter or AZURE_OPENAI_DALLE_KEY environment variable.")
        
        if not self.endpoint:
            raise ValueError("Endpoint is required. Provide via 'endpoint' parameter or AZURE_OPENAI_DALLE_ENDPOINT environment variable.")
        
        # Validate parameters
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model}. Supported models: {', '.join(self.SUPPORTED_MODELS)}")
        
        if size not in self.SUPPORTED_SIZES:
            raise ValueError(f"Unsupported size: {size}. Supported sizes: {', '.join(self.SUPPORTED_SIZES)}")
        
        if quality not in self.SUPPORTED_QUALITIES:
            raise ValueError(f"Unsupported quality: {quality}. Supported qualities: {', '.join(self.SUPPORTED_QUALITIES)}")
        
        if response_format not in ["url", "b64_json"]:
            raise ValueError("Response format must be 'url' or 'b64_json'")
        
        self.model = model
        self.size = size
        self.quality = quality
        self.response_format = response_format
        self.save_directory = save_directory
        
        # Create save directory if it doesn't exist
        if self.save_directory and not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
    
    def execute(self, prompt: str, n: int = 1, filename: Optional[str] = None) -> ToolResult:
        """
        Generate images based on the provided prompt.
        
        Args:
            prompt: The text description of the image to generate
            n: Number of images to generate (1-10)
            filename: Custom filename (without extension) to use for saving the image
                     If not provided, default name "generated_image_{index+1}" will be used
                     For multiple images, index will be appended to the filename
            
        Returns:
            URLs or base64 data of the generated images
        """
        try:
            if not prompt or not isinstance(prompt, str):
                return ToolResult.error_result("Prompt must be a non-empty string")
            
            # Limit n to a reasonable range
            n = max(1, min(10, n))
            
            # Prepare the API call
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            
            payload = {
                "prompt": prompt,
                "n": n,
                "size": self.size,
                "quality": self.quality,
                "response_format": self.response_format
            }
            
            # Make the API call
            response = requests.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Process the response
            result = {
                "prompt": prompt,
                "images": []
            }
            
            for i, image_data in enumerate(data.get("data", [])):
                image_url = image_data.get("url", "")
                image_b64 = image_data.get("b64_json", "")
                
                image_info = {
                    "index": i + 1
                }
                
                # Add URL or base64 data based on the response_format
                if self.response_format == "url" and image_url:
                    image_info["url"] = image_url
                    
                    # Save the image if a save directory is specified
                    if self.save_directory:
                        saved_path = self._save_image_from_url(image_url, i, filename)
                        image_info["saved_path"] = saved_path
                        
                elif self.response_format == "b64_json" and image_b64:
                    # For space efficiency, don't include the full base64 in the result
                    image_info["format"] = "base64"
                    
                    # Save the image if a save directory is specified
                    if self.save_directory:
                        saved_path = self._save_image_from_b64(image_b64, i, filename)
                        image_info["saved_path"] = saved_path
                
                result["images"].append(image_info)
            
            return ToolResult.success_result(result)
        
        except Exception as e:
            return ToolResult.error_result(f"Error generating image: {str(e)}")
    
    def _save_image_from_url(self, url: str, index: int, custom_filename: Optional[str] = None) -> str:
        """
        Download and save an image from a URL.
        
        Args:
            url: The image URL
            index: Image index for filename
            custom_filename: Optional custom filename (without extension)
            
        Returns:
            Path to the saved image
        """
        response = requests.get(url)
        response.raise_for_status()
        
        if custom_filename:
            # If multiple images are being generated, append index to avoid overwriting
            if index > 0:
                filename = os.path.join(self.save_directory, f"{custom_filename}_{index+1}.png")
            else:
                filename = os.path.join(self.save_directory, f"{custom_filename}.png")
        else:
            filename = os.path.join(self.save_directory, f"generated_image_{index+1}.png")
        
        with open(filename, "wb") as f:
            f.write(response.content)
        
        return filename
    
    def _save_image_from_b64(self, b64_data: str, index: int, custom_filename: Optional[str] = None) -> str:
        """
        Save an image from base64 data.
        
        Args:
            b64_data: Base64 encoded image data
            index: Image index for filename
            custom_filename: Optional custom filename (without extension)
            
        Returns:
            Path to the saved image
        """
        if custom_filename:
            # If multiple images are being generated, append index to avoid overwriting
            if index > 0:
                filename = os.path.join(self.save_directory, f"{custom_filename}_{index+1}.png")
            else:
                filename = os.path.join(self.save_directory, f"{custom_filename}.png")
        else:
            filename = os.path.join(self.save_directory, f"generated_image_{index+1}.png")
        
        with open(filename, "wb") as f:
            f.write(base64.b64decode(b64_data))
        
        return filename
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get a schema describing the tool's parameters.
        
        Returns:
            Dictionary representing the tool's parameter schema
        """
        return {
            "parameters": {
                "prompt": {
                    "type": "string",
                    "description": "A text description of the image to generate",
                    "required": True
                },
                "n": {
                    "type": "integer",
                    "description": "Number of images to generate (1-10)",
                    "required": False,
                    "default": 1
                },
                "filename": {
                    "type": "string",
                    "description": "Custom filename (without extension) to use for saving the image. For multiple images, an index will be appended.",
                    "required": False
                }
            },
            "returns": {
                "type": "object",
                "description": "URLs or paths to generated images"
            },
            "example": 'generate_image(prompt="A beautiful sunset over the ocean with sailboats on the horizon", filename="sunset_scene")'
        }