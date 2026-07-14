from google.adk.agents import Agent
from ..tools.retrieval_tool import retrieve_documents
retrieval_agent = Agent(name="retrieval_agent", model="gemini-2.5-flash", tools=[retrieve_documents])
