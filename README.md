# CopilotKit Memory MCP Experiment

This project is an experimental Model Context Protocol (MCP) server that integrates memory capabilities with CopilotKit. It provides a suite of tools including LangChain and Brave Search for enhanced AI assistance.

> **Important Note**: This tool is specifically designed to work with AI-powered IDEs like Windsurf, Cursor, and other similar environments. It will not function correctly in standard environments like Claude Desktop or regular chat interfaces.

## Project Structure

```
copilotkit-mem-mcp-exp/
├── server.py          # Main server implementation
├── tools/            # Tool implementations
│   ├── __init__.py
│   ├── base.py       # Base tool class
│   ├── brave_search.py
│   ├── langchain_tool.py
│   └── memory.py     # Memory management tool
├── .env.example      # Example environment variables
└── requirements.txt  # Project dependencies
```

## Features

- **Memory Integration**: Persistent memory system for maintaining context across interactions
- **LangChain Tools**: Advanced document processing, code analysis, and chain management
- **Brave Search**: Web search capabilities with context awareness
- **MCP Protocol**: Standard interface for AI model interactions

## Available Tools

### 1. Brave Search Tool
Search the web using the Brave Search API. Features include:
- Web search with customizable result count
- Rate limiting (1 request/second, 15,000 requests/month)
- Error handling and response validation

### 2. Memory Tool
Store and retrieve memories with metadata. Features include:
- Add memories with optional metadata
- Retrieve memories by key
- Search memories by content
- Delete memories
- List all stored memories

## AI IDE Integration

This tool is optimized for AI-powered Integrated Development Environments (IDEs) and provides enhanced functionality when used within these environments:

### Compatible IDEs
- Windsurf IDE
- Cursor IDE
- Other AI-powered development environments that support the Model Context Protocol (MCP)

### Features in AI IDEs
- Real-time context awareness of your codebase
- Intelligent tool suggestions based on your current task
- Seamless integration with the IDE's AI capabilities
- Enhanced memory management for storing and retrieving documentation

### Usage in AI IDEs
1. The tools automatically integrate with your IDE's AI assistant
2. Tools can be accessed through natural language queries to your AI assistant
3. Context from your current workspace is automatically provided to the tools

> **Note**: When using this tool outside of supported AI IDEs, many features will be limited or unavailable.

## Tool Integration Benefits for CopilotKit

### LangChain Integration
- **Document Processing**: Document loaders for various formats, text splitting for optimal chunking, and embeddings for semantic search
- **Memory Systems**: Conversation buffers, vector stores for semantic search, and structured memory for complex data
- **Agents & Tools**: Python REPL for code execution, custom tool creation, and agent frameworks for autonomous operations
- **Chain Management**: Sequential and parallel chain execution, error handling, and output parsing

Key use cases: Document Q&A, code analysis, contextual search, and autonomous task execution

### Brave Search Integration
- **Web Search**: Real-time web search capabilities for up-to-date information and context
- **Rate Limiting**: Built-in rate limiting for API management and cost control
- **Error Handling**: Robust error handling and response validation
- **Context Awareness**: Integration with CopilotKit's context system for relevant search results

Key use cases: Information retrieval, fact-checking, current events context, and web research assistance

## Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/copilotkit-mem-mcp-exp.git
cd copilotkit-mem-mcp-exp
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and add your Brave API key:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## API Usage

### Running the Server

```bash
# Start the server
python server.py

# Server will be available at http://localhost:8002
```

### Environment Variables

Required environment variables in `.env`:
```
BRAVE_API_KEY=your_brave_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # Required for LangChain features
```

### Making Requests

The server implements the Model Context Protocol (MCP). Here's how to use each tool:

#### Memory Tool
```json
{
  "tool_name": "memory",
  "parameters": {
    "action": "add|get|list",
    "key": "your_memory_key",
    "content": "content_to_store"  // for 'add' action
  }
}
```

#### Brave Search Tool
```json
{
  "tool_name": "brave_search",
  "parameters": {
    "query": "your search query",
    "count": 5  // optional, number of results
  }
}
```

#### LangChain Tool
```json
{
  "tool_name": "langchain",
  "parameters": {
    "action": "process_document|execute_code|search_memory",
    "content": "your content or code",
    "format": "pdf|markdown|text"  // for process_document
  }
}
```

## Adding New Tools

To add a new tool:

1. Create a new file in the `tools` directory
2. Implement the tool class inheriting from `BaseTool`
3. Override `get_tool_definition()` and `execute()`
4. Register the tool in `server.py`

Example:
```python
from tools.base import BaseTool, Tool, ToolType

class MyNewTool(BaseTool):
    def get_tool_definition(self) -> Tool:
        return Tool(
            name="my_tool",
            type=ToolType.CUSTOM,
            description="My new tool description",
            parameters={
                "param1": {
                    "type": "string",
                    "description": "Parameter description"
                }
            }
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # Implement tool logic here
        return {"result": "success"}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
