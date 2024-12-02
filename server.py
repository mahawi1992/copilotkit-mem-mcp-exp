import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime
import json
import aiohttp
import asyncio
from urllib.parse import urlparse
from memory import Memory, MemoryRequest, MemoryResponse

# Load environment variables
load_dotenv()

# FastAPI app with CORS
app = FastAPI(
    title="CopilotKit Memory MCP Experiment",
    description="A Model Context Protocol (MCP) server with memory integration for CopilotKit",
    version="0.1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    count: Optional[int] = 10

class SearchResponse(BaseModel):
    results: List[dict]
    total_count: int

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
        now = datetime.now().timestamp()
        if now - self.request_count['last_reset'] > 1:
            self.request_count['second'] = 0
            self.request_count['last_reset'] = now

        if (self.request_count['second'] >= self.per_second or 
            self.request_count['month'] >= self.per_month):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded"
            )

        self.request_count['second'] += 1
        self.request_count['month'] += 1

class BraveSearchClient:
    def __init__(self):
        self.api_key = os.getenv("BRAVE_API_KEY")
        if not self.api_key:
            raise ValueError("BRAVE_API_KEY environment variable is not set")
        self.base_url = "https://api.search.brave.com/res/v1"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        self.rate_limiter = RateLimiter()

    async def web_search(self, query: str, count: int = 10) -> dict:
        self.rate_limiter.check_limit()
        params = {
            "q": query,
            "count": min(count, 20)
        }
        response = requests.get(
            f"{self.base_url}/web/search",
            headers=self.headers,
            params=params
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Brave Search API error: {response.text}"
            )
        return response.json()

    async def local_search(self, query: str, count: int = 5) -> dict:
        self.rate_limiter.check_limit()
        # First get location IDs
        params = {
            "q": query,
            "count": min(count, 20),
            "result_filter": "locations"
        }
        response = requests.get(
            f"{self.base_url}/web/search",
            headers=self.headers,
            params=params
        )
        if response.status_code != 200:
            return await self.web_search(query, count)  # Fallback to web search

        data = response.json()
        location_ids = [r.get('id') for r in data.get('locations', {}).get('results', []) if r.get('id')]
        
        if not location_ids:
            return await self.web_search(query, count)  # Fallback to web search

        # Get POI details
        self.rate_limiter.check_limit()
        poi_response = requests.get(
            f"{self.base_url}/local/pois",
            headers=self.headers,
            params={'ids': location_ids}
        )
        
        if poi_response.status_code != 200:
            raise HTTPException(
                status_code=poi_response.status_code,
                detail=f"Brave Search API error: {poi_response.text}"
            )
            
        return poi_response.json()

# MCP Protocol Models
class ToolType(str, Enum):
    SEARCH = "search"
    CONTEXT = "context"
    CUSTOM = "custom"

class Tool(BaseModel):
    name: str
    type: ToolType
    description: str
    parameters: Dict[str, Any]
    version: str = "1.0.0"

class Context(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}
    timestamp: datetime = datetime.now()

class MCPRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Context] = None

class MCPResponse(BaseModel):
    result: Any
    context: Optional[Context] = None
    metadata: Dict[str, Any] = {}

# Enhanced Fetch Models
class FetchRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Union[str, Dict[str, Any]]] = None
    timeout: Optional[int] = 30
    follow_redirects: bool = True
    verify_ssl: bool = True

class FetchResponse(BaseModel):
    status: int
    headers: Dict[str, str]
    body: str
    url: str
    redirect_chain: List[str] = []
    timing: Dict[str, float] = {}
    error: Optional[str] = None

class FetchError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class FetchServer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.start_time: float = 0
    
    async def setup(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None
    
    def _validate_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False
    
    def _prepare_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        default_headers = {
            "User-Agent": "MCP-Fetch/1.0",
            "Accept": "*/*"
        }
        if headers:
            default_headers.update(headers)
        return default_headers
    
    def _prepare_body(self, body: Optional[Union[str, Dict[str, Any]]]) -> Optional[str]:
        if body is None:
            return None
        if isinstance(body, str):
            return body
        return json.dumps(body)
    
    async def fetch(self, request: FetchRequest) -> FetchResponse:
        await self.setup()
        
        if not self._validate_url(request.url):
            raise FetchError(f"Invalid URL: {request.url}", 400)
        
        if not self.session:
            raise FetchError("Session not initialized", 500)
        
        headers = self._prepare_headers(request.headers)
        body = self._prepare_body(request.body)
        redirect_chain = []
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with self.session.request(
                method=request.method,
                url=request.url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=request.timeout),
                allow_redirects=request.follow_redirects,
                ssl=request.verify_ssl
            ) as response:
                end_time = asyncio.get_event_loop().time()
                
                # Get redirect history
                if request.follow_redirects:
                    redirect_chain = [str(h.url) for h in response.history]
                
                response_body = await response.text()
                
                return FetchResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=response_body,
                    url=str(response.url),
                    redirect_chain=redirect_chain,
                    timing={
                        "total_seconds": end_time - start_time
                    }
                )
                
        except asyncio.TimeoutError:
            raise FetchError(f"Request timed out after {request.timeout} seconds", 408)
        except aiohttp.ClientError as e:
            raise FetchError(f"Request failed: {str(e)}", 500)
        except Exception as e:
            raise FetchError(f"Unexpected error: {str(e)}", 500)

# Tool Registry
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

# Initialize global variables
tool_registry = ToolRegistry()
brave_client = None
fetch_server = None
memory_store = Memory()

@app.on_event("startup")
async def startup_event():
    global brave_client, fetch_server
    
    try:
        # Initialize Brave Search client
        brave_client = BraveSearchClient()
        
        # Initialize fetch server
        fetch_server = FetchServer()
        await fetch_server.setup()
        
        # Register web search tool
        web_search_tool = Tool(
            name="brave_web_search",
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
            },
            version="1.0.0"
        )
        tool_registry.register(web_search_tool)
        
        # Register local search tool
        local_search_tool = Tool(
            name="brave_local_search",
            type=ToolType.SEARCH,
            description="Search for local businesses using Brave Search API",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 5
                }
            },
            version="1.0.0"
        )
        tool_registry.register(local_search_tool)

        # Register memory tool
        memory_tool = Tool(
            name="memory",
            type=ToolType.CUSTOM,
            description="Store and retrieve memories",
            parameters={
                "action": {
                    "type": "string",
                    "description": "Action to perform: add, get, search, delete, or list"
                },
                "key": {
                    "type": "string",
                    "description": "Key for the memory (required for add, get, delete)"
                },
                "value": {
                    "type": "string",
                    "description": "Value to store (required for add)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for search)"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata for the memory"
                }
            },
            version="1.0.0"
        )
        tool_registry.register(memory_tool)

        print("Tools registered successfully!")
    except Exception as e:
        print(f"Error during startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    if fetch_server:
        await fetch_server.cleanup()

@app.get("/mcp/tools")
def list_tools():
    tools = tool_registry.list_tools()
    print(f"Available tools: {[tool.name for tool in tools]}")
    return {"tools": tools}

@app.post("/mcp/execute")
async def execute_tool(request: MCPRequest) -> MCPResponse:
    """Execute a tool with the given parameters."""
    print(f"Executing tool: {request.tool_name}")  # Debug log
    print(f"Available tools: {[t.name for t in tool_registry.list_tools()]}")  # Debug log
    
    tool = tool_registry.get_tool(request.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool_name}")

    try:
        if tool.name == "brave_web_search":
            results = await brave_client.web_search(
                query=request.parameters["query"],
                count=request.parameters.get("count", 10)
            )
            return MCPResponse(result=results)
        elif tool.name == "brave_local_search":
            results = await brave_client.local_search(
                query=request.parameters["query"],
                count=request.parameters.get("count", 5)
            )
            return MCPResponse(result=results)
        elif tool.name == "memory":
            action = request.parameters.get("action")
            if action == "add":
                memory_store.add(
                    request.parameters["key"],
                    request.parameters["value"],
                    request.parameters.get("metadata")
                )
                return MCPResponse(result={"message": "Memory added successfully"})
            elif action == "get":
                memory = memory_store.get(request.parameters["key"])
                if not memory:
                    raise HTTPException(status_code=404, detail="Memory not found")
                return MCPResponse(result=memory)
            elif action == "search":
                results = memory_store.search(request.parameters["query"])
                return MCPResponse(result={"results": results})
            elif action == "delete":
                success = memory_store.delete(request.parameters["key"])
                if not success:
                    raise HTTPException(status_code=404, detail="Memory not found")
                return MCPResponse(result={"message": "Memory deleted successfully"})
            elif action == "list":
                memories = memory_store.list_all()
                return MCPResponse(result={"memories": memories})
            else:
                raise HTTPException(status_code=400, detail="Invalid action")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool.name}")
    except Exception as e:
        print(f"Error executing tool: {e}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not brave_client:
        raise HTTPException(
            status_code=500,
            detail="Brave Search client not initialized. Make sure BRAVE_API_KEY is set."
        )
    
    try:
        results = await brave_client.web_search(request.query, request.count)
        return SearchResponse(
            results=results.get("web", {}).get("results", []),
            total_count=results.get("web", {}).get("totalCount", 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/add")
async def add_memory(request: MemoryRequest) -> MemoryResponse:
    """Add a new memory."""
    if not request.key or not request.value:
        return MemoryResponse(success=False, message="Both key and value are required")
    
    memory_store.add(request.key, request.value, request.metadata)
    return MemoryResponse(success=True, message="Memory added successfully")

@app.get("/memory/get/{key}")
async def get_memory(key: str) -> MemoryResponse:
    """Get a memory by key."""
    memory = memory_store.get(key)
    if not memory:
        return MemoryResponse(success=False, message="Memory not found")
    return MemoryResponse(success=True, data=memory)

@app.post("/memory/search")
async def search_memories(request: MemoryRequest) -> MemoryResponse:
    """Search memories."""
    if not request.query:
        return MemoryResponse(success=False, message="Query is required")
    
    results = memory_store.search(request.query)
    return MemoryResponse(success=True, data={"results": results})

@app.delete("/memory/delete/{key}")
async def delete_memory(key: str) -> MemoryResponse:
    """Delete a memory by key."""
    success = memory_store.delete(key)
    if not success:
        return MemoryResponse(success=False, message="Memory not found")
    return MemoryResponse(success=True, message="Memory deleted successfully")

@app.get("/memory/list")
async def list_memories() -> MemoryResponse:
    """List all memories."""
    memories = memory_store.list_all()
    return MemoryResponse(success=True, data={"memories": memories})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
