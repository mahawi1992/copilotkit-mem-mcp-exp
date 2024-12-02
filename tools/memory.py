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
    def __init__(self, storage_path: str = "memories.json"):
        self.storage_path = storage_path
        self.memories: Dict[str, Memory] = {}
        self._load_memories()

    def _load_memories(self) -> None:
        """Load memories from JSON file if it exists."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = {
                        k: Memory(**v) for k, v in data.items()
                    }
            except Exception as e:
                print(f"Error loading memories: {e}")
                self.memories = {}

    def _save_memories(self) -> None:
        """Save memories to JSON file."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.dict() for k, v in self.memories.items()},
                    f,
                    indent=2,
                    ensure_ascii=False
                )
        except Exception as e:
            print(f"Error saving memories: {e}")

    def add(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.memories[key] = Memory(
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow().isoformat()
        )
        self._save_memories()

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
            self._save_memories()
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
    def __init__(self, storage_path: str = None):
        super().__init__()
        if storage_path is None:
            # Get the directory where memory.py is located
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to the project root
            project_root = os.path.dirname(current_dir)
            # Create a data directory if it doesn't exist
            data_dir = os.path.join(project_root, "data")
            os.makedirs(data_dir, exist_ok=True)
            # Set the storage path
            storage_path = os.path.join(data_dir, "memories.json")
        
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
                
                memory = self.store.get(key)
                if not memory:
                    return ToolResponse(error=f"Memory with key '{key}' not found")
                
                return ToolResponse(result=memory)

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
                
                success = self.store.delete(key)
                if not success:
                    return ToolResponse(error=f"Memory with key '{key}' not found")
                
                return ToolResponse(result={"message": "Memory deleted successfully"})

            elif action == "list":
                memories = self.store.list_all()
                return ToolResponse(result={"memories": memories})

            else:
                return ToolResponse(error=f"Unknown action: {action}")

        except Exception as e:
            return ToolResponse(error=str(e))
