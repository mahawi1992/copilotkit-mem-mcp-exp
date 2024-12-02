from typing import Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

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

class ToolResponse(BaseModel):
    """Response from a tool execution."""
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class BaseTool:
    def __init__(self):
        self.tool = self.get_tool_definition()
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition. Must be implemented by subclasses."""
        raise NotImplementedError
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute the tool with given parameters. Must be implemented by subclasses."""
        raise NotImplementedError
