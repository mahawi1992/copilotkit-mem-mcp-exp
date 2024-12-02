import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime
import json
import aiohttp
import asyncio
from urllib.parse import urlparse

# Import all tools
from tools.base import Tool, BaseTool, ToolType
from tools.brave_search import BraveSearchTool
from tools.memory import MemoryTool
# from tools.langchain_tool import LangChainToolWrapper  # Temporarily commented out

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

# Models
class Context(BaseModel):
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class MCPRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Context] = None

class MCPResponse(BaseModel):
    result: Any
    context: Optional[Context] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchRequest(BaseModel):
    query: str
    count: Optional[int] = 10

class SearchResponse(BaseModel):
    results: List[dict]
    total_count: int

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
    redirect_chain: List[str] = Field(default_factory=list)
    timing: Dict[str, float] = Field(default_factory=dict)
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
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def cleanup(self):
        if self.session:
            await self.session.close()
            self.session = None

    def _validate_url(self, url: str):
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                raise ValueError("Invalid URL")
        except Exception as e:
            raise FetchError(f"Invalid URL: {str(e)}")

    def _prepare_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        default_headers = {
            "User-Agent": "CopilotKit-MCP/1.0",
            "Accept": "*/*"
        }
        if headers:
            default_headers.update(headers)
        return default_headers

    def _prepare_body(self, body: Optional[Union[str, Dict[str, Any]]]) -> Optional[str]:
        if isinstance(body, dict):
            return json.dumps(body)
        return body

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        await self.setup()
        self._validate_url(request.url)
        
        headers = self._prepare_headers(request.headers)
        body = self._prepare_body(request.body)
        
        self.start_time = asyncio.get_event_loop().time()
        redirect_chain = []
        
        try:
            async with self.session.request(
                method=request.method,
                url=request.url,
                headers=headers,
                data=body,
                timeout=request.timeout,
                allow_redirects=request.follow_redirects,
                ssl=request.verify_ssl
            ) as response:
                end_time = asyncio.get_event_loop().time()
                body = await response.text()
                
                if request.follow_redirects:
                    redirect_chain = [str(resp.url) for resp in response.history]
                
                return FetchResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=body,
                    url=str(response.url),
                    redirect_chain=redirect_chain,
                    timing={"total_seconds": end_time - self.start_time}
                )
                
        except asyncio.TimeoutError:
            raise FetchError("Request timed out", 408)
        except Exception as e:
            raise FetchError(str(e))

# Global tools registry and servers
tools: Dict[str, BaseTool] = {}
fetch_server: Optional[FetchServer] = None

@app.on_event("startup")
async def startup_event():
    """Initialize and register tools."""
    global tools, fetch_server
    
    # Initialize fetch server
    fetch_server = FetchServer()
    await fetch_server.setup()
    
    # Initialize and register tools
    brave_tool = BraveSearchTool()
    memory_tool = MemoryTool()
    # langchain_tool = LangChainToolWrapper()  # Temporarily commented out
    
    tools = {
        brave_tool.get_tool_definition().name: brave_tool,
        memory_tool.get_tool_definition().name: memory_tool
        # langchain_tool.get_tool_definition().name: langchain_tool  # Temporarily commented out
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources."""
    if fetch_server:
        await fetch_server.cleanup()

@app.post("/mcp/tools")
async def list_tools() -> Dict[str, List[Tool]]:
    """List all available tools."""
    return {
        "tools": [tool.get_tool_definition() for tool in tools.values()]
    }

@app.post("/mcp/execute")
async def execute_tool(request: MCPRequest) -> MCPResponse:
    """Execute a tool with the given parameters."""
    if request.tool_name not in tools:
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
    
    try:
        tool = tools[request.tool_name]
        result = tool.execute(request.parameters)
        
        return MCPResponse(
            result=result,
            context=request.context,
            metadata={"tool": request.tool_name}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    """Perform a web search using Brave Search."""
    try:
        tool = tools.get("brave_search")
        if not tool:
            raise HTTPException(status_code=404, detail="Brave Search tool not found")
        
        results = tool.execute({
            "query": request.query,
            "count": request.count
        })
        
        return SearchResponse(
            results=results.get("results", []),
            total_count=len(results.get("results", []))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
