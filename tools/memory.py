from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime
from pydantic import BaseModel
from .base import BaseTool, Tool, ToolType, ToolResponse

class Memory(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}
    timestamp: str = ""

class MemoryStore:
    def __init__(self, storage_path: str = "memory.json"):
        self.storage_path = storage_path
        self.memories: List[Memory] = []
        self._load_memories()

    def _load_memories(self) -> None:
        """Load memories from JSON file if it exists."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = [Memory(**memory) for memory in data['result']['memories']]
            except Exception as e:
                print(f"Error loading memories: {e}")
                self.memories = []

    def _save_memories(self) -> None:
        """Save memories to JSON file."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "result": {
                        "memories": [memory.dict() for memory in self.memories]
                    },
                    "context": None,
                    "metadata": {}
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving memories: {e}")

    def add(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        memory = Memory(
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow().isoformat()
        )
        self.memories.append(memory)
        self._save_memories()

    def get_all(self) -> List[Memory]:
        return self.memories

    def search(self, query: str) -> List[Memory]:
        # Simple search implementation - can be enhanced later
        query = query.lower()
        return [memory for memory in self.memories if query in memory.content.lower()]

class MemoryTool(BaseTool):
    def __init__(self, storage_path: str = None):
        super().__init__()
        if storage_path is None:
            # Get the directory where memory.py is located
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to the project root
            project_root = os.path.dirname(current_dir)
            # Set the storage path to memory.json in root directory
            storage_path = os.path.join(project_root, "memory.json")
        
        self.store = MemoryStore(storage_path)

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

    def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
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
                
                metadata = parameters.get("metadata", {})
                self.store.add(key, content, metadata)
                return ToolResponse(result={"message": "Memory added successfully"})

            elif action == "get":
                key = parameters.get("key")
                if not key:
                    return ToolResponse(error="Key is required for get action")
                
                memories = self.store.get_all()
                for memory in memories:
                    if memory.content == key:
                        return ToolResponse(result=memory)
                
                return ToolResponse(error=f"Memory with key '{key}' not found")

            elif action == "search":
                query = parameters.get("query")
                if not query:
                    return ToolResponse(error="Query is required for search action")
                
                results = self.store.search(query)
                return ToolResponse(result={"results": results})

            elif action == "delete":
                key = parameters.get("key")
                if not key:
                    return ToolResponse(error="Key is required for delete action")
                
                memories = self.store.get_all()
                for i, memory in enumerate(memories):
                    if memory.content == key:
                        del memories[i]
                        self.store._save_memories()
                        return ToolResponse(result={"message": "Memory deleted successfully"})
                
                return ToolResponse(error=f"Memory with key '{key}' not found")

            elif action == "list":
                memories = self.store.get_all()
                return ToolResponse(result={"memories": memories})

            else:
                return ToolResponse(error=f"Unknown action: {action}")

        except Exception as e:
            return ToolResponse(error=str(e))
