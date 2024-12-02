from typing import Any, Dict, Optional, List
from tools.base import BaseTool, Tool, ToolType, ToolResponse

from langchain.tools import Tool as LangChainTool
from langchain.tools import BaseTool as LangChainBaseTool
from langchain.utilities.wikipedia import WikipediaAPIWrapper
from langchain.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain_community.tools.python.tool import PythonREPLTool
from langchain.chains import RetrievalQA


class LangChainToolWrapper(BaseTool):
    """Tool for executing LangChain tools."""

    def __init__(self):
        super().__init__()
        self._tools_cache: Dict[str, LangChainBaseTool] = {}
        self._vector_stores: Dict[str, Any] = {}
        self._conversation_memory = ConversationBufferMemory()
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    def get_tool_definition(self) -> Tool:
        return Tool(
            name="langchain",
            type=ToolType.CUSTOM,
            description="Executes various LangChain tools for document processing, code analysis, and knowledge retrieval",
            parameters={
                "tool_name": {
                    "type": "string",
                    "description": "Name of the LangChain tool to use (e.g., 'wikipedia', 'document_loader', 'code_analysis', 'vector_search', 'python_repl')",
                    "required": True
                },
                "input": {
                    "type": "string",
                    "description": "Input for the tool",
                    "required": True
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for the tool (e.g., file paths, search parameters)",
                    "required": False
                }
            }
        )

    def _get_tool(self, tool_name: str, context: Optional[Dict[str, Any]] = None) -> LangChainBaseTool:
        """Get or create a LangChain tool instance."""
        if tool_name not in self._tools_cache:
            if tool_name == "wikipedia":
                wikipedia = WikipediaAPIWrapper()
                self._tools_cache[tool_name] = WikipediaQueryRun(api_wrapper=wikipedia)
            elif tool_name == "python_repl":
                self._tools_cache[tool_name] = PythonREPLTool()
            elif tool_name == "document_loader":
                # Document loader will be created per request based on file type
                pass
            elif tool_name == "vector_search":
                # Vector store operations handled separately
                pass
            else:
                raise ValueError(f"Unsupported tool: {tool_name}")
        return self._tools_cache[tool_name]

    async def _load_document(self, file_path: str) -> List[Any]:
        """Load and split a document based on its type."""
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.md'):
            loader = UnstructuredMarkdownLoader(file_path)
        else:
            loader = TextLoader(file_path)
        
        documents = loader.load()
        return self._text_splitter.split_documents(documents)

    async def _create_vector_store(self, documents: List[Any], store_name: str):
        """Create a vector store from documents."""
        embeddings = OpenAIEmbeddings()
        vector_store = FAISS.from_documents(documents, embeddings)
        self._vector_stores[store_name] = vector_store
        return vector_store

    async def _vector_search(self, query: str, store_name: str, k: int = 4) -> List[str]:
        """Search the vector store for relevant documents."""
        if store_name not in self._vector_stores:
            raise ValueError(f"Vector store '{store_name}' not found")
        
        vector_store = self._vector_stores[store_name]
        results = vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in results]

    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute the LangChain tool."""
        try:
            tool_name = parameters["tool_name"]
            tool_input = parameters["input"]
            context = parameters.get("context", {})

            if tool_name == "document_loader":
                file_path = context.get("file_path")
                if not file_path:
                    raise ValueError("file_path is required for document_loader")
                documents = await self._load_document(file_path)
                if context.get("create_vector_store"):
                    store_name = context.get("store_name", "default")
                    await self._create_vector_store(documents, store_name)
                return ToolResponse(result={"num_documents": len(documents)})

            elif tool_name == "vector_search":
                store_name = context.get("store_name", "default")
                k = context.get("k", 4)
                results = await self._vector_search(tool_input, store_name, k)
                return ToolResponse(result=results)

            elif tool_name == "python_repl":
                tool = self._get_tool(tool_name)
                result = await tool.ainvoke(tool_input)
                return ToolResponse(result=result)

            else:
                tool = self._get_tool(tool_name)
                result = await tool.ainvoke(tool_input)
                return ToolResponse(result=result)

        except Exception as e:
            return ToolResponse(error=str(e))
