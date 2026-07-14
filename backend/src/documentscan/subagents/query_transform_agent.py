from google.adk.agents import Agent
query_transform_agent = Agent(name="query_transform_agent", model="gemini-2.5-flash", instruction="Parse entities from unstructured prompts.")
