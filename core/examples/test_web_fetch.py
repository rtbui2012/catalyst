
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import json

load_dotenv()

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from core.tools.web_search import WebSearchTool
from core.tools.web_fetch import WebFetchTool

# Get API key from environment variable for security
# You can set these by adding them to your .env file
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', 'YOUR_GOOGLE_API_KEY')
GOOGLE_CX_ID = os.environ.get('GOOGLE_CX_ID', 'YOUR_GOOGLE_CX_ID')

def main():
    # Create the web search tool
    web_search_tool = WebSearchTool(
        search_engine="google",
        api_key=GOOGLE_API_KEY,
        cx_id=GOOGLE_CX_ID,
        max_results=3,
        include_snippets=True
    )
    
    # Create the web fetch tool
    web_fetch_tool = WebFetchTool(
        max_content_length=5000  # Limit content length
    )
    
    # Example search query
    search_query = "latest AI breakthroughs 2025"
    print(f"Searching for: {search_query}")
    
    # Perform the search
    search_result = web_search_tool.execute(search_query)
    
    if not search_result.success:
        print(f"Search failed: {search_result.error}")
        return
    
    # Save search results
    with open('examples/output/search_results.json', 'w') as f:
        json.dump(search_result.data, f, indent=2)
    
    print(f"Found {len(search_result.data['items'])} search results.")
    
    # Fetch content from the first search result link
    if search_result.data['items']:
        first_result = search_result.data['items'][0]
        url = first_result['link']
        title = first_result['title']
        
        print(f"\nFetching content from the first result:\n{title}\n{url}")
        
        # Try different extraction methods
        for extract_type in ["summary", "main", "full"]:
            print(f"\nExtracting {extract_type} content...")
            fetch_result = web_fetch_tool.execute(url=url, extract_type=extract_type)
            
            if fetch_result.success:
                # Save fetched content
                with open(f'examples/output/fetched_{extract_type}.json', 'w') as f:
                    json.dump(fetch_result.data, f, indent=2)
                
                print(f"Content length: {fetch_result.data['length']} characters")
                print(f"Content preview:\n{fetch_result.data['content'][:300]}...")
            else:
                print(f"Fetch failed: {fetch_result.error}")
    else:
        print("No search results found.")

if __name__ == "__main__":
    main()

