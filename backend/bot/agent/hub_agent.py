import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from dotenv import load_dotenv

load_dotenv()

def build_hub_agent(tools):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        api_key=os.getenv("GEMINI_API_KEY")
    )
    
    system_prompt = """You are the 'Hub Agent', an AI Tournament Manager for a Street Fighter 6 tournament.
You receive natural language commands from the tournament organizer via the dashboard.
Your job is to execute these commands by using the tools provided to you.
You can look up active matches, look up registered players to find their Discord IDs, and create Discord match threads.
If the organizer asks you to call a match, you should:
1. Lookup the active matches to find the match details.
2. Lookup the players to find their Discord IDs.
3. Use the create_discord_thread_tool to create a thread and ping them.
4. Reply with a clear summary of what you did.

If you don't find the players in the database, let the organizer know they haven't registered yet!
"""
    
    # Prepend system message using prompt
    return create_react_agent(llm, tools, prompt=system_prompt)
