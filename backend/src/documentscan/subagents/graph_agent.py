from google.adk.agents import Agent
from ..tools.graph_tool import graph_traverse
graph_agent = Agent(name="graph_agent", model="gemini-2.5-flash", tools=[graph_traverse])
