from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from .base import BaseTool, Tool, ToolType, ToolResponse

class Memory(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}
    timestamp: str = ""

class MemoryStore:
    def __init__(self):
        self.memories: Dict[str, Memory] = {}

    def add(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.memories[key] = Memory(
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow().isoformat()
        )

    def get(self, key: str) -> Optional[Memory]:
        return self.memories.get(key)

    def search(self, query: str) -> List[Dict[str, Any]]:
        results = []
        for key, memory in self.memories.items():
            if query.lower() in memory.content.lower():
                results.append({
                    "key": key,
                    "content": memory.content,
                    "metadata": memory.metadata,
                    "timestamp": memory.timestamp
                })
        return results

    def delete(self, key: str) -> bool:
        if key in self.memories:
            del self.memories[key]
            return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": k,
                "content": v.content,
                "metadata": v.metadata,
                "timestamp": v.timestamp
            }
            for k, v in self.memories.items()
        ]

class MemoryTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.store = MemoryStore()
        self.memories = {}

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="memory",
            type=ToolType.CUSTOM,
            description="Store and retrieve memories",
            parameters={
                "action": {
                    "type": "string",
                    "description": "Action to perform: add, get, search, delete, or list",
                    "enum": ["add", "get", "search", "delete", "list"]
                },
                "key": {
                    "type": "string",
                    "description": "Key for the memory"
                },
                "content": {
                    "type": "string",
                    "description": "Content to store"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata"
                }
            }
        )

    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute the Memory tool with given parameters."""
        try:
            action = parameters.get("action")
            if not action:
                return ToolResponse(error="Action parameter is required")

            if action == "add":
                key = parameters.get("key")
                content = parameters.get("content")
                if not key or not content:
                    return ToolResponse(error="Key and content are required for add action")
                
                memory = Memory(
                    content=content,
                    metadata=parameters.get("metadata", {}),
                    timestamp=datetime.now().isoformat()
                )
                self.memories[key] = memory
                return ToolResponse(result={"message": "Memory added successfully"})

            elif action == "get":
                key = parameters.get("key")
                if not key:
                    return ToolResponse(error="Key is required for get action")
                
                memory = self.memories.get(key)
                if not memory:
                    return ToolResponse(error=f"Memory with key {key} not found")
                
                return ToolResponse(result=memory.dict())

            elif action == "list":
                memories = {
                    key: memory.dict() 
                    for key, memory in self.memories.items()
                }
                return ToolResponse(result={"memories": list(memories.values())})

            elif action == "delete":
                key = parameters.get("key")
                if not key:
                    return ToolResponse(error="Key is required for delete action")
                
                if key not in self.memories:
                    return ToolResponse(error=f"Memory with key {key} not found")
                
                del self.memories[key]
                return ToolResponse(result={"message": f"Memory {key} deleted successfully"})

            elif action == "search":
                query = parameters.get("query")
                if not query:
                    return ToolResponse(error="Query is required for search action")
                
                results = self.store.search(query)
                return ToolResponse(result={"results": results})

            else:
                return ToolResponse(error=f"Unknown action: {action}")

        except Exception as e:
            return ToolResponse(error=str(e))
