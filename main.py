from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from tools.base import Tool, BaseTool
from tools.brave_search import BraveSearchTool
from tools.memory import MemoryTool
from tools.langchain_tool import LangChainToolWrapper

# Load environment variables
load_dotenv()

# Global tools registry
tools: Dict[str, BaseTool] = {}

# FastAPI app
app = FastAPI(
    title="MCP Tools Server",
    description="A modular server implementing the Model Context Protocol",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Context(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}
    timestamp: str = ""

class MCPRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Context] = None

class MCPResponse(BaseModel):
    result: Any
    context: Optional[Context] = None
    metadata: Dict[str, Any] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize and register tools."""
    try:
        global tools
        
        # Register tools
        tool_instances = [
            BraveSearchTool(),
            MemoryTool(),
            LangChainToolWrapper()
        ]
        
        for tool in tool_instances:
            tools[tool.tool.name] = tool
        
        print("Tools registered successfully!")
    except Exception as e:
        print(f"Error during startup: {e}")

@app.get("/mcp/tools")
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return [tool.tool for tool in tools.values()]

@app.post("/mcp/execute")
async def execute_tool(request: MCPRequest) -> MCPResponse:
    """Execute a tool with the given parameters."""
    try:
        if request.tool_name not in tools:
            raise HTTPException(status_code=404, detail=f"Tool {request.tool_name} not found")
        
        tool = tools[request.tool_name]
        result = await tool.execute(request.parameters)
        
        if result.error:
            raise HTTPException(status_code=400, detail=result.error)
        
        return MCPResponse(
            result=result.result,
            context=request.context,
            metadata=result.metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
