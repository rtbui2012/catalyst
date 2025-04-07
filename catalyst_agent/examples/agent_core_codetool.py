import sys
import os
import textwrap
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from catalyst_agent import AgentCore, AgentConfig
from catalyst_agent.tools.code_execution import DynamicCodeExecutionTool
from catalyst_agent.tools.web_search import WebSearchTool
from catalyst_agent.tools.web_fetch import WebFetchTool
from catalyst_agent.tools.image_generation import ImageGenerationTool
from catalyst_agent.tools.package_manager import PackageInstallerTool
from catalyst_agent.tools.download_file import DownloadFileTool

if __name__ == "__main__":
    # Initialize the agent with a configuration
    config = AgentConfig(blob_storage_path='./output', tool_discovery_enabled=False)
    
    # Add current date to config metadata to help with temporal understanding
    current_date = datetime.now().strftime("%Y-%m-%d")
    config.metadata = {
        "current_date": current_date
    }
    
    print(f"==== Temporal Context ====")
    print(f"Current date: {current_date}")
    print(f"==========================")
    
    # Create an instance of the agent
    agent = AgentCore(config)
    
    # Initialize the code execution tool
    code_execution_tool = DynamicCodeExecutionTool()

    # Create the web search tool configured for Google
    web_search_tool = WebSearchTool(
        search_engine="google",
        api_key=os.environ.get('GOOGLE_API_KEY', 'YOUR_GOOGLE_API_KEY'),
        cx_id=os.environ.get('GOOGLE_CX_ID', 'YOUR_GOOGLE_CX_ID'),
        max_results=5,
        include_snippets=True
    )
    
    # Initialize the web fetch tool to retrieve content from web pages
    web_fetch_tool = WebFetchTool(
        max_content_length=8000  # Limit content length to avoid overwhelming the agent
    )

    # Initialize the image generation tool with Azure OpenAI DALL-E API credentials
    image_tool = ImageGenerationTool(
        api_key=os.environ.get("AZURE_OPENAI_DALLE_KEY"),
        endpoint=os.environ.get("AZURE_OPENAI_DALLE_ENDPOINT"),
        size="1024x1024",  # Options: 1024x1024, 1792x1024, 1024x1792
        quality="standard",  # Options: standard, hd
        save_directory='./generated_images'  # Directory to save generated images
    )

    download_tool = DownloadFileTool(
        default_output_dir='./blob_storage',  # Directory to save downloaded files
    )

    python_package_installer_tool = PackageInstallerTool()    
    
    # Register the tools with the agent
    agent.register_tool(code_execution_tool)
    agent.register_tool(python_package_installer_tool)
    agent.register_tool(web_search_tool)
    agent.register_tool(download_tool)


    # # Example of a task that requires a tool (code execution)
    # computational_task = """
    # Calculate the first 10 Fibonacci numbers and save them to a file named 'fibonacci.txt'.
    # """
    
    # # Example of a task that doesn't require a tool (pure language generation)
    # creative_task = """
    # Chart the median household income per year in the US since 2005.
    # """

    task = "Analyze the iris dataset and summarize the results in a markdown file. Include a plots to illustrate your conclusions."
   
    # # Check if the computational task can be accomplished
    # print("COMPUTATIONAL TASK EVALUATION:")
    # response = agent.can_accomplish(computational_task)
    # print(f"Solution possible response:\n{response}")
    
    # # Check if the creative task can be accomplished
    # print("\nCREATIVE TASK EVALUATION:")
    # response = agent.can_accomplish(creative_task)
    # print(f"Solution possible response:\n{response}")
    
    # # Example of processing the creative task (which could be done without tools)
    # print("\nEXECUTING CREATIVE TASK (with unnecessary tool usage):")
    response = agent.process_message(task)
    print(f"Solution:\n{response}")
