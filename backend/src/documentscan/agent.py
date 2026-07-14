from google.adk.agents import Agent
from .subagents.query_transform_agent import query_transform_agent
from .subagents.retrieval_agent import retrieval_agent
from .subagents.graph_agent import graph_agent
from .tools.sql_tool import sql_query_tool

root_agent = Agent(
    name="documentscan_root",
    model="gemini-2.5-flash",
    description="Scan billing documents",
    instruction="Orchestrator core reasoning logic system.",
    sub_agents=[query_transform_agent, retrieval_agent, graph_agent],
    tools=[sql_query_tool],
)
