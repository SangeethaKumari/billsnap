from fastmcp import FastMCP
from .tools.retrieval_tool import retrieve_documents
from .tools.graph_tool import graph_traverse

mcp = FastMCP("documentscan")
mcp.tool(retrieve_documents)
mcp.tool(graph_traverse)

if __name__ == "__main__":
    mcp.run(transport="stdio")
