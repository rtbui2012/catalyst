import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from agentic.core.tools.web_search import WebSearchTool

# Get API key from environment variable for security
# You can set this environment variable before running the script
# Or replace with your actual value for testing (not recommended for production)
BING_API_KEY = os.environ.get('BING_API_KEY', 'YOUR_BING_API_KEY')

# Create the web search tool configured for Bing
web_search_tool = WebSearchTool(
    search_engine="bing",
    api_key=BING_API_KEY,
    max_results=5,
    include_snippets=True
)

# Test with a specific query
query = "Super Bowl 2025"
print(f"Searching for: {query}")

try:
    results = web_search_tool.execute(query)
    if results.success:
        print(f"Search results:\n{results.data}")
        
        # Print each result in a more readable format
        if results.data["items"]:
            print("\nFormatted results:")
            for i, item in enumerate(results.data["items"], 1):
                print(f"\n{i}. {item['title']}")
                print(f"   URL: {item['link']}")
                if "snippet" in item:
                    print(f"   Snippet: {item['snippet']}")
        else:
            print("\nNo results found.")
    else:
        print(f"Search failed: {results.error}")
except Exception as e:
    print(f"Error during search: {str(e)}")