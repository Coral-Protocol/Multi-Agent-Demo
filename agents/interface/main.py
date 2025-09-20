import urllib.parse
from dotenv import load_dotenv
import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor

REQUEST_QUESTION_TOOL = "request-question"
ANSWER_QUESTION_TOOL = "answer-question"
MAX_CHAT_HISTORY = 3
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 8000
SLEEP_INTERVAL = 1
ERROR_RETRY_INTERVAL = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    print("[VERBOSE] Starting configuration loading...")
    runtime = os.getenv("CORAL_ORCHESTRATION_RUNTIME", None)
    print(f"[VERBOSE] CORAL_ORCHESTRATION_RUNTIME: {runtime}")
    
    if runtime is None:
        print("[VERBOSE] Runtime not found, loading .env file...")
        load_dotenv()
        print("[VERBOSE] .env file loaded successfully")
    else:
        print("[VERBOSE] Runtime environment detected, skipping .env file")
    
    print("[VERBOSE] Building configuration dictionary...")
    config = {
        "runtime": os.getenv("CORAL_ORCHESTRATION_RUNTIME", None),
        "coral_connection_url": os.getenv("CORAL_CONNECTION_URL"),
        "agent_id": os.getenv("CORAL_AGENT_ID"),
        "model_name": os.getenv("MODEL_NAME"),
        "model_provider": os.getenv("MODEL_PROVIDER"),
        "api_key": os.getenv("MODEL_API_KEY"),
        "model_temperature": float(os.getenv("MODEL_TEMPERATURE", DEFAULT_TEMPERATURE)),
        "model_token": int(os.getenv("MODEL_TOKEN_LIMIT", DEFAULT_MAX_TOKENS)),
        "base_url": os.getenv("BASE_URL")
    }
    
    print(f"[VERBOSE] Configuration loaded:")
    print(f"[VERBOSE]   - runtime: {config['runtime']}")
    print(f"[VERBOSE]   - agent_id: {config['agent_id']}")
    print(f"[VERBOSE]   - model_name: {config['model_name']}")
    print(f"[VERBOSE]   - model_provider: {config['model_provider']}")
    print(f"[VERBOSE]   - api_key: {'***' if config['api_key'] else None}")
    print(f"[VERBOSE]   - model_temperature: {config['model_temperature']}")
    print(f"[VERBOSE]   - model_token: {config['model_token']}")
    print(f"[VERBOSE]   - base_url: {config['base_url']}")
    
    print("[VERBOSE] Validating required fields...")
    required_fields = ["coral_connection_url", "agent_id", "model_name", "model_provider", "api_key"]
    missing = [field for field in required_fields if not config[field]]
    if missing:
        print(f"[VERBOSE] ERROR: Missing required fields: {missing}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    print("[VERBOSE] All required fields present")
    
    print("[VERBOSE] Validating model parameters...")
    if not 0 <= config["model_temperature"] <= 2:
        print(f"[VERBOSE] ERROR: Invalid temperature: {config['model_temperature']}")
        raise ValueError(f"Model temperature must be between 0 and 2, got {config['model_temperature']}")
    print(f"[VERBOSE] Temperature validation passed: {config['model_temperature']}")
    
    if config["model_token"] <= 0:
        print(f"[VERBOSE] ERROR: Invalid token limit: {config['model_token']}")
        raise ValueError(f"Model token must be positive, got {config['model_token']}")
    print(f"[VERBOSE] Token limit validation passed: {config['model_token']}")
    
    print("[VERBOSE] Configuration loading completed successfully")
    return config

def get_tools_description(tools: List[Any]) -> str:
    print(f"[VERBOSE] Starting tools description generation for {len(tools)} tools...")
    
    descriptions = []
    for i, tool in enumerate(tools):
        print(f"[VERBOSE] Processing tool {i+1}/{len(tools)}: {tool.name}")
        tool_desc = f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        descriptions.append(tool_desc)
        print(f"[VERBOSE] Tool description generated: {tool_desc[:100]}...")
    
    result = "\n".join(descriptions)
    print(f"[VERBOSE] Tools description generation completed. Total length: {len(result)} characters")
    return result

def format_chat_history(chat_history: List[Dict[str, str]]) -> str:
    print(f"[VERBOSE] Starting chat history formatting with {len(chat_history)} conversations...")
    
    if not chat_history:
        print("[VERBOSE] No chat history found, returning default message")
        return "No previous chat history available."
    
    print(f"[VERBOSE] Processing {len(chat_history)} chat history entries...")
    history_str = "Previous Conversations (use this to resolve ambiguous references like 'it'):\n"
    
    for i, chat in enumerate(chat_history, 1):
        print(f"[VERBOSE] Processing conversation {i}/{len(chat_history)}")
        print(f"[VERBOSE] User input length: {len(chat.get('user_input', ''))} chars")
        print(f"[VERBOSE] Agent response length: {len(chat.get('response', ''))} chars")
        
        history_str += f"Conversation {i}:\n"
        history_str += f"User: {chat['user_input']}\n"
        history_str += f"Agent: {chat['response']}\n\n"
    
    print(f"[VERBOSE] Chat history formatting completed. Total formatted length: {len(history_str)} characters")
    return history_str

async def get_user_input(runtime: str, agent_tools: Dict[str, Any]) -> str:
    print(f"[VERBOSE] Starting user input retrieval. Runtime mode: {runtime is not None}")
    
    if runtime is not None:
        print(f"[VERBOSE] Using runtime mode - invoking {REQUEST_QUESTION_TOOL} tool")
        print(f"[VERBOSE] Available agent tools: {list(agent_tools.keys())}")
        try:
            print("[VERBOSE] Calling request_question tool with message prompt...")
            user_input = await agent_tools[REQUEST_QUESTION_TOOL].ainvoke({
                "message": "How can I assist you today? "
            })
            print(f"[VERBOSE] Successfully received input from runtime tool: {len(str(user_input))} chars")
        except Exception as e:
            print(f"[VERBOSE] ERROR: Failed to invoke request_question tool: {str(e)}")
            logger.error(f"Error invoking request_question tool: {str(e)}")
            raise
    else:
        print("[VERBOSE] Using interactive mode - prompting user directly")
        user_input = input("How can I assist you today? ").strip()
        print(f"[VERBOSE] Raw user input received: '{user_input}'")
        
        if not user_input:
            print("[VERBOSE] Empty input detected, using default message")
            user_input = "No input provided"
    
    print(f"[VERBOSE] Final processed user input: {user_input}")
    logger.info(f"User input: {user_input}")
    return user_input

async def send_response(runtime: str, agent_tools: Dict[str, Any], response: str) -> None:
    print(f"[VERBOSE] Starting response sending. Runtime mode: {runtime is not None}")
    print(f"[VERBOSE] Response length: {len(response)} characters")
    print(f"[VERBOSE] Response preview: {response[:200]}...")
    
    logger.info(f"Agent response: {response}")
    
    if runtime is not None:
        print(f"[VERBOSE] Using runtime mode - invoking {ANSWER_QUESTION_TOOL} tool")
        print(f"[VERBOSE] Available agent tools: {list(agent_tools.keys())}")
        try:
            print("[VERBOSE] Calling answer_question tool with response...")
            await agent_tools[ANSWER_QUESTION_TOOL].ainvoke({
                "response": response
            })
            print("[VERBOSE] Successfully sent response via runtime tool")
        except Exception as e:
            print(f"[VERBOSE] ERROR: Failed to invoke answer_question tool: {str(e)}")
            logger.error(f"Error invoking answer_question tool: {str(e)}")
            raise
    else:
        print("[VERBOSE] Interactive mode - response logged only (no runtime tool)")
    
    print("[VERBOSE] Response sending completed")

async def create_agent(coral_tools: List[Any]) -> AgentExecutor:
    print(f"[VERBOSE] Starting agent creation with {len(coral_tools)} coral tools...")
    
    print("[VERBOSE] Generating tools description...")
    coral_tools_description = get_tools_description(coral_tools)
    print(f"[VERBOSE] Tools description generated: {len(coral_tools_description)} characters")
    
    print("[VERBOSE] Creating chat prompt template...")
    query = os.getenv('USER_REQUEST')
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""Your primary role is to plan tasks sent by the user and send clear instructions to other agents to execute them, focusing solely on questions about the Coral Server, its tools: {coral_tools_description}, and registered agents. 
            Always use {{chat_history}} to understand the context of the question along with the user's instructions. 
            Think carefully about the question, analyze its intent, and create a detailed plan to address it, considering the roles and capabilities of available agents, description and their tools. 

            Your task is to coordinate with the other agents to find results for the query: "{query}".

            Follow the steps in order:
            1. Call list_agents to get all connected agents and their descriptions.
            2. Check if the question is directly related to Coral Server (e.g., list agents, tool details). For such requests, use appropriate tools to retrieve and return the information.
            3. If the question requires interaction with other agents, analyze the user's intent using chat history to resolve ambiguous references (e.g., 'it'). Create a detailed plan to delegate tasks:
                - Identify which agents are relevant based on their descriptions and tools.
                - If the task requires sequential processing (e.g., one agent's output is needed by another), structure the plan to specify the order of agent interactions.
                - Call create_thread('threadName': 'user_request', 'participantIds': [IDs, including self]) to initiate collaboration.
                - For each selected agent:
                - If not in thread, call add_participant(threadId=..., 'participantIds': [agent ID]).
                - Send clear instructions via send_message(threadId=..., content="instruction", mentions=[agent ID]). Instructions should specify the task, any dependencies (e.g., "use output from Agent X"), and expected output format.
                - Use wait_for_mentions(timeoutMs=60000) up to 5 times to collect responses.
                - Store responses for synthesis.
            4. Synthesize responses into clear, concise, self contained 'search results'.
            5. Return the answer, by calling the send-search-result tool, once for each relevant result you get back from other agents. You can send these as soon as you have good results. 

            """
        ),
        ("human", "{user_input}"),
        ("placeholder", "{agent_scratchpad}")
    ])
    print("[VERBOSE] Chat prompt template created successfully")

    print("[VERBOSE] Initializing chat model...")
    print(f"[VERBOSE] Model configuration:")
    print(f"[VERBOSE]   - model: {os.getenv('MODEL_NAME')}")
    print(f"[VERBOSE]   - provider: {os.getenv('MODEL_PROVIDER')}")
    print(f"[VERBOSE]   - api_key: {'***' if os.getenv('MODEL_API_KEY') else None}")
    print(f"[VERBOSE]   - temperature: {float(os.getenv('MODEL_TEMPERATURE', DEFAULT_TEMPERATURE))}")
    print(f"[VERBOSE]   - max_tokens: {int(os.getenv('MODEL_MAX_TOKENS', DEFAULT_MAX_TOKENS))}")
    print(f"[VERBOSE]   - base_url: {os.getenv('MODEL_BASE_URL', None)}")
    
    model = init_chat_model(
        model=os.getenv("MODEL_NAME"),
        model_provider=os.getenv("MODEL_PROVIDER"),
        api_key=os.getenv("MODEL_API_KEY"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", DEFAULT_TEMPERATURE)),
        max_tokens=int(os.getenv("MODEL_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        base_url=os.getenv("MODEL_BASE_URL", None)
    )
    print("[VERBOSE] Chat model initialized successfully")

    print("[VERBOSE] Creating tool calling agent...")
    agent = create_tool_calling_agent(model, coral_tools, prompt)
    print("[VERBOSE] Tool calling agent created successfully")
    
    print("[VERBOSE] Creating agent executor with verbose=True and return_intermediate_steps=True")
    executor = AgentExecutor(agent=agent, tools=coral_tools, verbose=True, return_intermediate_steps=True)
    print("[VERBOSE] Agent executor created successfully")
    
    return executor

async def main():
    """Main function to run the agent in a continuous loop with chat history."""
    print("[VERBOSE] ========== STARTING MAIN FUNCTION ==========")
    
    try:
        print("[VERBOSE] Loading configuration...")
        config = load_config()
        print("[VERBOSE] Configuration loaded successfully")

        print("[VERBOSE] Preparing Coral Server connection parameters...")
        
        coral_server_url = config["coral_connection_url"]
        print(f"[VERBOSE] Coral server URL constructed: {coral_server_url}")
        logger.info(f"Connecting to Coral Server: {coral_server_url}")

        print("[VERBOSE] Setting up MCP client...")
        timeout = float(os.getenv("TIMEOUT_MS", "30000"))
        print(f"[VERBOSE] Using timeout: {timeout}ms")
        
        client = MultiServerMCPClient(
            connections={
                "coral": {
                    "transport": "sse",
                    "url": coral_server_url,
                    "timeout": timeout,
                    "sse_read_timeout": timeout,
                }
            }
        )
        print("[VERBOSE] MCP client created")
        logger.info("Coral Server connection established")

        print("[VERBOSE] Retrieving coral tools...")
        coral_tools = await client.get_tools(server_name="coral")
        print(f"[VERBOSE] Retrieved {len(coral_tools)} coral tools:")
        for i, tool in enumerate(coral_tools):
            print(f"[VERBOSE]   Tool {i+1}: {tool.name}")
        logger.info(f"Retrieved {len(coral_tools)} coral tools")

        print("[VERBOSE] Checking runtime mode and required tools...")
        if config["runtime"] is not None:
            print("[VERBOSE] Runtime mode detected - validating required tools...")
            required_tools = [REQUEST_QUESTION_TOOL, ANSWER_QUESTION_TOOL]
            available_tools = [tool.name for tool in coral_tools]
            print(f"[VERBOSE] Required tools: {required_tools}")
            print(f"[VERBOSE] Available tools: {available_tools}")
            
            for tool_name in required_tools:
                if tool_name not in available_tools:
                    error_message = f"Required tool '{tool_name}' not found in coral_tools"
                    print(f"[VERBOSE] ERROR: {error_message}")
                    logger.error(error_message)
                    raise ValueError(error_message)
            print("[VERBOSE] All required tools found")
        else:
            print("[VERBOSE] Interactive mode - no runtime tool validation needed")
        
        print("[VERBOSE] Creating agent tools dictionary...")
        agent_tools = {tool.name: tool for tool in coral_tools}
        print(f"[VERBOSE] Agent tools dictionary created with {len(agent_tools)} tools")
        
        print("[VERBOSE] Creating agent executor...")
        agent_executor = await create_agent(coral_tools)
        logger.info("Agent executor created")

        print("[VERBOSE] Initializing chat history...")
        chat_history: List[Dict[str, str]] = []
        print(f"[VERBOSE] Chat history initialized (max size: {MAX_CHAT_HISTORY})")

        print("[VERBOSE] ========== ENTERING MAIN LOOP ==========")
        loop_iteration = 0
        
        while True:
            try:
                loop_iteration += 1
                print(f"[VERBOSE] --- Loop iteration {loop_iteration} ---")
                
                print("[VERBOSE] Getting user input...")
                user_input = await get_user_input(config["runtime"], agent_tools)
                
                print("[VERBOSE] Formatting chat history...")
                formatted_history = format_chat_history(chat_history)
                print(f"[VERBOSE] Chat history formatted: {len(formatted_history)} characters")
                
                print("[VERBOSE] Invoking agent executor...")
                print(f"[VERBOSE] Agent executor input:")
                print(f"[VERBOSE]   - user_input: {user_input}")
                print(f"[VERBOSE]   - chat_history length: {len(formatted_history)} chars")
                
                result = await agent_executor.ainvoke({
                    "user_input": user_input,
                    "agent_scratchpad": [],
                    "chat_history": formatted_history
                })
                
                print(f"[VERBOSE] Agent executor completed. Result keys: {list(result.keys())}")
                response = result.get('output', 'No output returned')
                print(f"[VERBOSE] Extracted response: {len(response)} characters")
                
                print("[VERBOSE] Sending response...")
                await send_response(config["runtime"], agent_tools, response)

                print("[VERBOSE] Updating chat history...")
                chat_history.append({"user_input": user_input, "response": response})
                print(f"[VERBOSE] Chat history updated. Current size: {len(chat_history)}")
                
                if len(chat_history) > MAX_CHAT_HISTORY:
                    removed = chat_history.pop(0)
                    print(f"[VERBOSE] Chat history size exceeded {MAX_CHAT_HISTORY}, removed oldest entry")
                    print(f"[VERBOSE] Removed entry preview: {removed['user_input'][:50]}...")
                
                print(f"[VERBOSE] Sleeping for {SLEEP_INTERVAL} seconds...")
                await asyncio.sleep(SLEEP_INTERVAL)
                print(f"[VERBOSE] Loop iteration {loop_iteration} completed successfully")
                
            except Exception as e:
                print(f"[VERBOSE] ERROR in agent loop iteration {loop_iteration}: {str(e)}")
                print(f"[VERBOSE] Exception type: {type(e).__name__}")
                logger.error(f"Error in agent loop: {str(e)}")
                print(f"[VERBOSE] Sleeping for {ERROR_RETRY_INTERVAL} seconds before retry...")
                await asyncio.sleep(ERROR_RETRY_INTERVAL)
                
    except Exception as e:
        print(f"[VERBOSE] FATAL ERROR in main function: {str(e)}")
        print(f"[VERBOSE] Fatal exception type: {type(e).__name__}")
        logger.error(f"Fatal error in main: {str(e)}")
        print("[VERBOSE] ========== MAIN FUNCTION TERMINATING ==========")
        raise

if __name__ == "__main__":
    asyncio.run(main())
