import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from core.agent import AgentCore, AgentConfig
from core.tools.image_generation import ImageGenerationTool

if __name__ == "__main__":
    # Initialize the agent with a configuration
    config = AgentConfig()
    
    # Add current date to config metadata
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_year = str(datetime.now().year)
    config.metadata = {
        "current_date": current_date,
        "current_year": current_year 
    }
    
    print(f"==== Temporal Context ====")
    print(f"Current date: {current_date}")
    print(f"Current year: {current_year}")
    print(f"==========================")
    
    # Create an instance of the agent
    agent = AgentCore(config)
    
    # Create a directory to save generated images
    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Initialize the image generation tool with Azure OpenAI DALL-E API credentials
    image_tool = ImageGenerationTool(
        api_key=os.environ.get("AZURE_OPENAI_DALLE_KEY"),
        endpoint=os.environ.get("AZURE_OPENAI_DALLE_ENDPOINT"),
        size="1024x1024",  # Options: 1024x1024, 1792x1024, 1024x1792
        quality="standard",  # Options: standard, hd
        save_directory=images_dir
    )
    
    # Register the tool with the agent
    agent.register_tool(image_tool)
    
    # Example of image generation task
    image_generation_task = """
    Generate an image of a futuristic city with flying cars and tall skyscrapers against a sunset sky.
    Save it as 'future_city'.
    """
    
    # Process the image generation task
    print("\nEXECUTING IMAGE GENERATION TASK:")
    response = agent.process_message(image_generation_task)
    print(f"Response:\n{response}")
    
    # Example of a more detailed image generation task with custom filename
    detailed_image_task = """
    Generate an image of a cozy cafe in Paris with people sitting outside, a view of the Eiffel Tower in the distance, 
    and autumn leaves falling. The scene should have a warm color palette. Name the file 'paris_cafe_autumn'.
    """
    
    # Process the detailed image task
    print("\nEXECUTING DETAILED IMAGE GENERATION TASK:")
    response = agent.process_message(detailed_image_task)
    print(f"Response:\n{response}")
    
    print(f"\nGenerated images are saved in: {images_dir}")