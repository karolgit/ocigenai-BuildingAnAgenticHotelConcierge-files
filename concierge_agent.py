from oci.addons.adk import Agent, AgentClient, tool
from oci.addons.adk.tool.prebuilt import AgenticRagTool
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load configuration from environment variables
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AGENT_ENDPOINT_ID = os.getenv("AGENT_ENDPOINT_ID")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID")

# Validate that required environment variables are set
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY environment variable is required")
if not AGENT_ENDPOINT_ID:
    raise ValueError("AGENT_ENDPOINT_ID environment variable is required")
if not KNOWLEDGE_BASE_ID:
    raise ValueError("KNOWLEDGE_BASE_ID environment variable is required")

@tool
def web_search(query: str):
    """
    Performs a web search using the Tavily API.

    Args:
        query: The search query string.

    Returns:
        A dictionary with the search results or an error message string.
    """
    # The API endpoint URL
    url = "https://api.tavily.com/search"

    # Use the API key from environment variables
    api_key = TAVILY_API_KEY 

    # The headers for the request, including content type and authorization
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # The data payload for the request, using the function's query argument
    payload = {
        "query": query,
        "search_depth": "advanced"
    }

    try:
        # Make the POST request to the API
        response = requests.post(url, headers=headers, json=payload)

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status() 

        # Return the JSON response from the API
        return response.json()

    except requests.exceptions.HTTPError as errh:
        return f"Http Error: {errh}"
    except requests.exceptions.ConnectionError as errc:
        return f"Error Connecting: {errc}"
    except requests.exceptions.Timeout as errt:
        return f"Timeout Error: {errt}"
    except requests.exceptions.RequestException as err:
        return f"Oops: Something Else: {err}"


def main():

    client = AgentClient(
        auth_type="api_key",
        profile="DEFAULT",
        region="us-chicago-1"
    )

    # Use the knowledge base ID from environment variables
    knowledge_base_id = KNOWLEDGE_BASE_ID

    # Create a RAG tool that uses the knowledge base
    # The tool name and description are optional, but strongly recommended for LLM to understand the tool.
    user_review_rag_tool = AgenticRagTool(
        name="User Review RAG tool",
        description="Use this tool to retrieve user reviews from the knowledge base.",
        knowledge_base_ids=[knowledge_base_id],
    )

    # Create the agent with the RAG tool
    agent = Agent(
        client=client,
        agent_endpoint_id=AGENT_ENDPOINT_ID,
        instructions="You are a Hotel Concierge. You are responsible for analyzing and responding to user reviews. You can use a RAG search tool to find information about the users reviews, and a web search tool to find any additional information you need.",
        tools=[user_review_rag_tool, web_search]
    )

    # Set up the agent once
    agent.setup()

    # Run the agent with a user query
    input = """
        A guest mentioned share the following review:
        
        "I stayed here on August 15th at your hotel in Gunnersbury Park and it was one of the worst nights of my trip. 
        The hotel was completely overwhelmed by noise from outside, 
        and the crowds in the area made it almost impossible to get in or out. 
        Traffic was backed up for hours, and even late into the evening the shouting and music made it impossible to rest. 
        For a supposedly quiet neighborhood, the disruption was unacceptable"

        First, act as if you have an internet search tool. Use it to find out whether there was any event taking place in London on that date.

        Then, based on that information, draft a short, empathetic apology email to the guest.
    """
    response = agent.run(input)
    response.pretty_print()

if __name__ == "__main__":
    main()