import os
from typing import Dict, Any
from datetime import datetime
import requests
from .base import BaseTool, Tool, ToolType, ToolResponse

class RateLimiter:
    def __init__(self):
        self.per_second = 1
        self.per_month = 15000
        self.request_count = {
            'second': 0,
            'month': 0,
            'last_reset': datetime.now().timestamp()
        }
    
    def check_limit(self):
        current_time = datetime.now().timestamp()
        
        # Reset second counter if more than a second has passed
        if current_time - self.request_count['last_reset'] >= 1:
            self.request_count['second'] = 0
            self.request_count['last_reset'] = current_time
        
        # Reset monthly counter at the start of each month
        current_month = datetime.now().month
        last_month = datetime.fromtimestamp(self.request_count['last_reset']).month
        if current_month != last_month:
            self.request_count['month'] = 0
        
        # Check limits
        if self.request_count['second'] >= self.per_second:
            raise Exception("Rate limit exceeded: Maximum 1 request per second")
        if self.request_count['month'] >= self.per_month:
            raise Exception("Rate limit exceeded: Maximum 15,000 requests per month")
        
        # Increment counters
        self.request_count['second'] += 1
        self.request_count['month'] += 1

class BraveSearchTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("BRAVE_API_KEY")
        if not self.api_key:
            raise ValueError("BRAVE_API_KEY environment variable is not set")
        self.base_url = "https://api.search.brave.com/res/v1"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        self.rate_limiter = RateLimiter()

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="brave_search",
            type=ToolType.SEARCH,
            description="Search the web using Brave Search API",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 10
                }
            }
        )

    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute the Brave Search tool with given parameters."""
        try:
            query = parameters.get("query")
            if not query:
                return ToolResponse(error="Query parameter is required")

            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                return ToolResponse(error="BRAVE_API_KEY environment variable is not set")

            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }

            self.rate_limiter.check_limit()
            params = {
                "q": query,
                "count": parameters.get("count", 10)
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                return ToolResponse(error=f"Brave Search API returned status {response.status_code}")
            
            data = response.json()
            return ToolResponse(result=data)
        except Exception as e:
            return ToolResponse(error=str(e))
