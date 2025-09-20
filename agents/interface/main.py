import urllib.parse
from dotenv import load_dotenv
import os, json, asyncio, traceback
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools import Tool
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_tools_description(tools):
    return "\n".join(
        f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        for tool in tools
    )

async def ask_human_tool(question: str) -> str:
    print(f"Agent asks: {question}")
    response = input("Your response: ")
    return response

async def create_agent(coral_tools, agent_tools, runtime):
    coral_tools_description = get_tools_description(coral_tools)
    
    if runtime is not None:
        agent_tools_for_description = [
            tool for tool in coral_tools if tool.name in agent_tools
        ]
        agent_tools_description = get_tools_description(agent_tools_for_description)
        combined_tools = coral_tools + agent_tools_for_description
        user_request_tool = "request_question"
        user_answer_tool = "answer_question"
        print(agent_tools_description)
    else:
        # For other runtimes (e.g., devmode), agent_tools is a list of Tool objects
        agent_tools_description = get_tools_description(agent_tools)
        combined_tools = coral_tools + agent_tools
        user_request_tool = "ask_human"
        user_answer_tool = "ask_human"

    query = os.getenv("USER_REQUEST")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""
            Your task is to collaborate with other agents to get useful results from a 'search query' from users.

            Your query/question to return results for is: "{query}"

            Follow these steps in order:
            1. Use `list_agents` to list all connected agents and get their descriptions.
            2. Create threads & message those agents to get useful results to return
            3. Whenever you have concise, self contained information to return, you can call send-search-result with markdown text to send it back to the user. You can call it multiple times as more useful results come in

            **You MUST NEVER finish the chain**
            
            These are the list of coral tools: {coral_tools_description}
            These are the list of agent tools: {agent_tools_description}

            **You MUST NEVER finish the chain**"""
        ),
        ("placeholder", "{agent_scratchpad}")
    ])
    print(prompt)

    model = init_chat_model(
        model=os.getenv("MODEL_NAME"),
        model_provider=os.getenv("MODEL_PROVIDER"),
        api_key=os.getenv("MODEL_API_KEY"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", 0.0)),
        max_tokens=int(os.getenv("MODEL_MAX_TOKENS", 8000)),
        base_url=os.getenv("MODEL_BASE_URL", None)
    )
    agent = create_tool_calling_agent(model, combined_tools, prompt)
    return AgentExecutor(agent=agent, tools=combined_tools, verbose=True)

async def main():
    runtime = os.getenv("CORAL_ORCHESTRATION_RUNTIME", None)
    if runtime is None:
        load_dotenv()

    base_url = os.getenv("CORAL_SSE_URL")
    agentID = os.getenv("CORAL_AGENT_ID")

    coral_params = {
        "agentId": agentID,
        "agentDescription": "An agent that takes user input and interacts with other agents to fulfill requests"
    }

    query_string = urllib.parse.urlencode(coral_params)

    CORAL_SERVER_URL = f"{base_url}?{query_string}"
    logger.info(f"Connecting to Coral Server: {CORAL_SERVER_URL}")

    client = MultiServerMCPClient(
        connections={
            "coral": {
                "transport": "sse",
                "url": CORAL_SERVER_URL,
                "timeout": 300000,
                "sse_read_timeout": 300000,
            }
        }
    )
    logger.info("Coral Server Connection Established")

    coral_tools = await client.get_tools(server_name="coral")
    logger.info(f"Coral tools count: {len(coral_tools)}")
    
    agent_tools = []
    agent_executor = await create_agent(coral_tools, agent_tools, runtime)

    while True:
        try:
            logger.info("Starting new agent invocation")
            await agent_executor.ainvoke({"agent_scratchpad": []})
            logger.info("Completed agent invocation, restarting loop")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in agent loop: {str(e)}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
