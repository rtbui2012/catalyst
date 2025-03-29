import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from core.tools.web_search import WebSearchTool

# Get API key from environment variable for security
# You can set this by running: set BING_API_KEY=your_key_here (on Windows)
# Or export BING_API_KEY=your_key_here (on Linux/Mac)
api_key = os.environ.get("GOOGLE_API_KEY")
cx_id = os.environ.get("CX_ID")

# Create the web search tool with your preferred configuration
web_search_tool = WebSearchTool(
    search_engine="google",  # Bing provides better results than DuckDuckGo for most queries
    cx_id=cx_id,
    api_key=api_key,
    max_results=5
)

try:
    results = web_search_tool.execute("Trump")
    print(f"Search results: {results.data}")
except Exception as e:
    print(f"Error during search: {str(e)}")
