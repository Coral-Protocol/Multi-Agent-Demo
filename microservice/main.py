import os
from fastapi import FastAPI, Query, Body, HTTPException
from pydantic import BaseModel
import asyncio
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

app = FastAPI()

OPENAI_KEY = os.getenv("OPENAI_KEY")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY")
GH_PAT = os.getenv("GH_PAT")

CORAL_SERVER_HOST = os.getenv("CORAL_SERVER_HOST", "http://localhost:5555")
THIS_HOST = os.getenv("THIS_HOST", "http://localhost:8080")

customTools = {
    "search-result": {
        "transport": {
            "type": "http",
            "url": THIS_HOST + "/mcp/search-result"
        },
        "toolSchema": {
          "name": "send-search-result",
          "description": "Send a single result of your search. You can call this multiple times as you find more info.",
          "inputSchema": {
            "type": "object",
            "properties": {
              "result": {
                "type": "string",
                "description": "The text of the result, as markdown"
              }
            },
            "required": ["result"]
          }
        }
    }
}
# we use the same agent graph, so lets keep it here
agentGraphRequest = {
    "agents": [
        {},
        {
            "id": {"name": "firecrawl", "version": "0.0.1"},
            "name": "firecrawl",
            "coralPlugins": [],
            "provider": {"type": "local", "runtime": "executable"},
            "blocking": True,
            "options": {
                "MODEL_API_KEY": {"type": "string", "value": OPENAI_KEY},
                "FIRECRAWL_API_KEY": {"type": "string", "value": FIRECRAWL_KEY},
            },
            "customToolAccess": [],
        },
        {
            "id": {"name": "github", "version": "0.0.1"},
            "name": "github",
            "coralPlugins": [],
            "provider": {"type": "local", "runtime": "executable"},
            "blocking": True,
            "options": {
                "MODEL_API_KEY": {"type": "string", "value": OPENAI_KEY},	
                "GITHUB_PERSONAL_ACCESS_TOKEN": {"type": "string", "value": GH_PAT},	
            },
            "customToolAccess": [],
        },
    ],
    "groups": [["interface", "firecrawl", "github"]],
        "customTools": customTools
}

def create_app_graph_request(query: str):
    interface_agent = {
        "id": {"name": "interface", "version": "0.0.1"},
        "name": "interface",
        "coralPlugins": [],
        "provider": {"type": "local", "runtime": "executable"},
        "blocking": True,
        "options": {
            "MODEL_API_KEY": {"type": "string", "value": OPENAI_KEY},
            "USER_REQUEST": {"type": "string", "value": query}
        },
        "customToolAccess": ["search-result"],
    }
    final_req = agentGraphRequest
    final_req["agents"][0] = interface_agent
    print("FINAL_REQ")
    print(json.dumps(final_req, indent=4))
    return final_req




pending_searches: dict[str, asyncio.Future] = {}

@app.post("/search")
async def search(q: str = Query(..., description="Search query")):
    future_id = "FROM_SESSION"


    payload = {
        "privacyKey": "priv",
        "applicationId": "app",
        "sessionId": "",
        "agentGraphRequest": create_app_graph_request(q),
    }
    print("PAYLOAD")
    print(json.dumps(payload, indent=4))
    # 3️⃣ POST request to coral server (to create our session)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(CORAL_SERVER_HOST + "/api/v1/sessions", json=payload)
            data = response.json()
            future_id = data.get("sessionId")
        except httpx.RequestError as e:
            print(f"Error sending POST to http://todo/: {e}")

    loop = asyncio.get_event_loop()
    future = loop.create_future()
    pending_searches[future_id] = future

    try:
        # Wait for someone to resolve it via /mcp
        result = await future
    finally:
        # Clean up whether it was resolved or cancelled
        pending_searches.pop(future_id, None)
    
    return {"result": result}


class SearchResult(BaseModel):
    result: str 

@app.post("/mcp/search-result/{sessionId}/{agentId}")
async def mcp_search_result(sessionId: str, agentId: str, body: SearchResult):
    print("Got result from agent: ", body.result)
    # Lookup pending search by sessionId
    future = pending_searches.get(sessionId)
    if not future:
        raise HTTPException(status_code=404, detail="No pending request for this session")

    if not future.done():
        future.set_result(body.result)
    return "Success"
